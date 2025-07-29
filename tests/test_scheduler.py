from unittest.mock import MagicMock

import pytest
from flask import Flask
from freezegun import freeze_time

import scheduler as scheduler_mod
from models import Group, Host, JobHistory, Schedule, db


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite://", SQLALCHEMY_TRACK_MODIFICATIONS=False
    )
    db.init_app(app)
    with app.app_context():
        db.create_all()
    yield app


@pytest.fixture(autouse=True)
def clear_jobs():
    yield
    scheduler_mod.scheduler.remove_all_jobs()


def test_disabled_schedules_not_loaded(app):
    with app.app_context():
        s1 = Schedule(
            name="enabled",
            cron="* * * * *",
            enabled=True,
            firmware_path="fw",
            dry_run=True,
        )
        s2 = Schedule(
            name="disabled",
            cron="* * * * *",
            enabled=False,
            firmware_path="fw",
            dry_run=True,
        )
        db.session.add_all([s1, s2])
        db.session.commit()
        s1_id, s2_id = s1.id, s2.id
        db.session.remove()

    scheduler_mod.scheduler.app = app
    with app.app_context():
        scheduler_mod.load_schedules()
    job_ids = [job.id for job in scheduler_mod.scheduler.get_jobs()]
    assert f"schedule_{s1_id}" in job_ids
    assert f"schedule_{s2_id}" not in job_ids


def test_parse_cron_fields():
    trig = scheduler_mod._parse_cron("0 3 * * 1-5")
    assert str(trig.fields[6]) == "0"  # minute
    assert str(trig.fields[5]) == "3"  # hour
    assert str(trig.fields[4]) == "1-5"  # day_of_week


def test_schedule_creates_history_and_enqueues(app, monkeypatch):
    with app.app_context():
        group = Group(name="g")
        h1 = Host(hostname="a", idrac_ip="1")
        h2 = Host(hostname="b", idrac_ip="2")
        group.hosts.extend([h1, h2])
        sched = Schedule(
            name="s",
            cron="* * * * *",
            enabled=True,
            target_group=group,
            firmware_path="fw",
            dry_run=True,
        )
        db.session.add_all([group, h1, h2, sched])
        db.session.commit()
        sched_id = sched.id
        db.session.remove()

    scheduler_mod.init_scheduler(app)

    calls = []
    monkeypatch.setattr(
        scheduler_mod.firmware_task,
        "delay",
        lambda *a, **k: calls.append(a),
    )
    monkeypatch.setattr(
        "tasks.firmware_task.delay",
        lambda *a, **k: calls.append(a),
    )

    with freeze_time("2024-01-01"):
        scheduler_mod.firmware_job(sched_id)

    with app.app_context():
        hist = JobHistory.query.filter_by(schedule_id=sched_id).first()
        assert hist is not None
        assert hist.status == "QUEUED"

    assert len(calls) == 2
