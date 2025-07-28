"""APScheduler job integration"""

from flask_apscheduler import APScheduler
from models import db, Schedule, JobHistory, Host, Group
from datetime import datetime
from update import apply_firmware
import utils
import config
import logging

logger = logging.getLogger("firmware_maestro")

scheduler = APScheduler()

def firmware_job(schedule_id: int):
    schedule = Schedule.query.get(schedule_id)
    if not schedule or not schedule.enabled:
        return
    history = JobHistory(schedule_id=schedule_id, start_time=datetime.utcnow())
    db.session.add(history)
    db.session.commit()

    group = schedule.target_group
    hosts = group.hosts if group else Host.query.all()
    success = 0
    failed = 0
    for host in hosts:
        result = apply_firmware(host, schedule.firmware_path, schedule.dry_run)
        if result == "SUCCESS" or result == "DRYRUN":
            success += 1
            host.last_status = "OK"
        else:
            failed += 1
            host.last_status = "ERROR"
        host.last_message = result
        db.session.add(host)
        db.session.commit()
    history.end_time = datetime.utcnow()
    if failed:
        history.status = "PARTIAL" if success else "FAILED"
    else:
        history.status = "SUCCESS"
    db.session.add(history)
    db.session.commit()

def load_schedules():
    for s in Schedule.query.filter_by(enabled=True).all():
        if s.cron:
            scheduler.add_job(
                id=f"schedule_{s.id}",
                func=firmware_job,
                trigger="cron",
                **{k:v for k,v in _parse_cron(s.cron).items() if v is not None},
                args=[s.id],
                replace_existing=True,
            )
        elif s.interval_minutes:
            scheduler.add_job(
                id=f"schedule_{s.id}",
                func=firmware_job,
                trigger="interval",
                minutes=s.interval_minutes,
                args=[s.id],
                replace_existing=True,
            )

def _parse_cron(cron_expr: str):
    """Very simple cron parser 'm h dom mon dow' -> dict"""
    parts = cron_expr.split()
    fields = ["minute","hour","day","month","day_of_week"]
    return dict(zip(fields, parts))
