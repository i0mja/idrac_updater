"""Celery tasks for asynchronous operations."""

from __future__ import annotations

import datetime as dt
import logging

from celery import shared_task

from models import Host, JobHistory, db
from update import apply_firmware

log = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=3)
def firmware_task(self, host_id: int, sched_id: int, history_id: int) -> None:
    """Apply firmware on a single host."""
    host = Host.query.get(host_id)
    history = JobHistory.query.get(history_id)
    if not host or not history:
        log.error("Invalid task references host=%s history=%s", host_id, history_id)
        return
    try:
        result = apply_firmware(
            host, history.schedule.firmware_path, history.schedule.dry_run
        )
        host.last_status = "OK" if result in ("SUCCESS", "DRYRUN") else "ERROR"
        host.last_message = result
    except Exception as exc:  # pragma: no cover - raised for autoretry
        log.exception("Update failed for host %s", host_id)
        host.last_status = "ERROR"
        host.last_message = f"ERROR: {exc}"
        raise
    finally:
        host.last_updated = dt.datetime.utcnow()
        db.session.commit()
