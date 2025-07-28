import os
import sys
import types
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# stub redfish client so update.py imports
if 'redfish' not in sys.modules:
    fake = types.ModuleType('redfish')
    class Dummy: pass
    fake.RedfishClient = Dummy
    sys.modules['redfish'] = fake

from flask import Flask
if not hasattr(Flask, 'before_first_request'):
    Flask.before_first_request = lambda self, f: f

import pytest
from bs4 import BeautifulSoup

from app import app as flask_app
import config
from models import db, Host, Group, Schedule, JobHistory
import utils
import scheduler
import update

@pytest.fixture(autouse=True)
def setup_app(monkeypatch):
    flask_app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
    with flask_app.app_context():
        db.create_all()
        yield
        db.drop_all()

def get_client(monkeypatch, role):
    groups_map = {
        'Admin': [config.ADMIN_GROUP],
        'Operator': [config.OPERATOR_GROUP],
        'Viewer': []
    }
    monkeypatch.setattr(utils, 'get_user_groups', lambda u: groups_map[role])
    return flask_app.test_client()


def test_dashboard_requires_auth():
    client = flask_app.test_client()
    resp = client.get('/')
    assert resp.status_code == 401


def test_admin_access(monkeypatch):
    client = get_client(monkeypatch, 'Admin')
    assert client.get('/', headers={'X-Remote-User':'test'}).status_code == 200
    assert client.get('/settings', headers={'X-Remote-User':'test'}).status_code == 200
    assert client.get('/schedules', headers={'X-Remote-User':'test'}).status_code == 200


def test_operator_access(monkeypatch):
    client = get_client(monkeypatch, 'Operator')
    assert client.get('/', headers={'X-Remote-User':'test'}).status_code == 200
    assert client.get('/schedules', headers={'X-Remote-User':'test'}).status_code == 200
    assert client.get('/settings', headers={'X-Remote-User':'test'}).status_code == 403


def test_viewer_access(monkeypatch):
    client = get_client(monkeypatch, 'Viewer')
    assert client.get('/', headers={'X-Remote-User':'test'}).status_code == 200
    assert client.get('/schedules', headers={'X-Remote-User':'test'}).status_code == 403
    assert client.get('/settings', headers={'X-Remote-User':'test'}).status_code == 403


def test_navigation_menu(monkeypatch):
    client = get_client(monkeypatch, 'Admin')
    resp = client.get('/', headers={'X-Remote-User':'test'})
    soup = BeautifulSoup(resp.data, 'html.parser')
    nav = soup.find('nav').get_text()
    for item in ['Dashboard','Hosts','Schedules','Settings']:
        assert item in nav


def test_hosts_inline_policy(monkeypatch):
    client = get_client(monkeypatch, 'Viewer')
    with flask_app.app_context():
        db.session.add(Host(hostname='h1', idrac_ip='1.2.3.4'))
        db.session.commit()
    resp = client.get('/hosts', headers={'X-Remote-User':'test'})
    soup = BeautifulSoup(resp.data, 'html.parser')
    assert soup.find('input', {'name':'policy'}) is not None


def test_load_schedules_adds_jobs(monkeypatch):
    client = get_client(monkeypatch, 'Admin')
    with flask_app.app_context():
        g = Group(name='g')
        db.session.add(g)
        db.session.commit()
        sched = Schedule(name='s', firmware_path='/fw', interval_minutes=5, target_group=g)
        db.session.add(sched)
        db.session.commit()
        called = {}
        monkeypatch.setattr(scheduler.scheduler, 'add_job', lambda *a, **k: called.setdefault('ok', True))
        scheduler.load_schedules()
        assert called.get('ok')


def test_apply_firmware_dry_run():
    host = Host(hostname='h1', idrac_ip='1.2.3.4')
    assert update.apply_firmware(host, '/fw', dry_run=True) == 'DRYRUN'


def test_firmware_job_records_history(monkeypatch):
    client = get_client(monkeypatch, 'Admin')
    with flask_app.app_context():
        h = Host(hostname='h1', idrac_ip='1.2.3.4')
        g = Group(name='g1', hosts=[h])
        db.session.add_all([h, g])
        db.session.commit()
        sched = Schedule(name='sched', firmware_path='/fw', interval_minutes=5, target_group=g)
        db.session.add(sched)
        db.session.commit()
        monkeypatch.setattr(update, 'apply_firmware', lambda h,p,d=False: 'SUCCESS')
        monkeypatch.setattr(scheduler, 'apply_firmware', lambda h,p,d=False: 'SUCCESS')
        scheduler.firmware_job(sched.id)
        hist = JobHistory.query.one()
        assert hist.status == 'SUCCESS'
        assert h.last_status == 'OK'


@pytest.mark.xfail(reason='Setup wizard not implemented')
def test_setup_wizard_steps(monkeypatch):
    client = get_client(monkeypatch, 'Admin')
    assert client.get('/setup', headers={'X-Remote-User':'test'}).status_code == 200


@pytest.mark.xfail(reason='Notifications integration missing')
def test_notifications(monkeypatch):
    client = get_client(monkeypatch, 'Admin')
    assert False

