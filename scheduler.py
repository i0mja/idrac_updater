"""APScheduler job integration"""

import logging
from datetime import datetime

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from flask import current_app
from flask_apscheduler import APScheduler

from models import Host, JobHistory, Schedule, db
from tasks import firmware_task

logger = logging.getLogger("firmware_maestro")

scheduler = APScheduler()


def _parse_cron(expr: str) -> CronTrigger:
    """Return a validated CronTrigger."""

    try:
        return CronTrigger.from_crontab(expr)
    except ValueError as exc:
        raise ValueError(f"Invalid cron expression '{expr}'") from exc


def init_scheduler(app) -> None:
    """Initialize scheduler with jobs from the database."""

    scheduler.init_app(app)
    scheduler.start()
    with app.app_context():
        load_schedules()


def firmware_job(schedule_id: int) -> None:
    """Enqueue firmware update tasks for all hosts in the schedule."""

    app = scheduler.app or current_app
    with app.app_context():
        try:
            with db.session.begin():
                schedule = db.session.get(Schedule, schedule_id)
                if not schedule or not schedule.enabled:
                    return

                history = JobHistory(
                    schedule_id=schedule_id, start_time=datetime.utcnow()
                )
                db.session.add(history)
                db.session.flush()

                host_ids = (
                    [h.id for h in schedule.target_group.hosts]
                    if schedule.target_group
                    else [h.id for h in Host.query.all()]
                )
                for host_id in host_ids:
                    firmware_task.delay(host_id, schedule_id, history.id)
                history.end_time = datetime.utcnow()
                history.status = "QUEUED"
        except Exception:
            logger.exception("Failed scheduling firmware job %s", schedule_id)
            db.session.rollback()
            with db.session.begin():
                history.status = "FAILED"
                history.end_time = datetime.utcnow()
                db.session.add(history)


def load_schedules() -> None:
    """Load enabled schedules into the APScheduler instance."""

    for s in Schedule.query.filter_by(enabled=True).all():
        if s.cron:
            trigger = _parse_cron(s.cron)
        elif s.interval_minutes:
            trigger = IntervalTrigger(minutes=s.interval_minutes)
        else:
            continue

        scheduler.add_job(
            id=f"schedule_{s.id}",
            func=firmware_job,
            trigger=trigger,
            args=[s.id],
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
            max_instances=1,
        )
