"""Firmware update logic via Redfish + vCenter maintenance mode"""

import logging
import ssl
import time
from typing import Optional

from pyVim.connect import Disconnect, SmartConnect
from pyVmomi import vim
from requests.exceptions import RequestException

import config
from models import Host
from redfish_client import RedfishClient

logger = logging.getLogger("firmware_maestro")


def _enter_maintenance(hostname: str):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    si = SmartConnect(
        host=config.VCENTER_HOST,
        user=config.VCENTER_USER,
        pwd=config.VCENTER_PASS,
        sslContext=ctx,
    )
    content = si.RetrieveContent()
    host_obj = next(
        (
            h
            for h in content.viewManager.CreateContainerView(
                content.rootFolder, [vim.HostSystem], True
            ).view
            if h.name == hostname
        ),
        None,
    )
    if host_obj:
        if not host_obj.inMaintenanceMode:
            task = host_obj.EnterMaintenanceMode_Task(timeout=0)
            task_result = task.info.state
    Disconnect(si)


def _exit_maintenance(hostname: str):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    si = SmartConnect(
        host=config.VCENTER_HOST,
        user=config.VCENTER_USER,
        pwd=config.VCENTER_PASS,
        sslContext=ctx,
    )
    content = si.RetrieveContent()
    host_obj = next(
        (
            h
            for h in content.viewManager.CreateContainerView(
                content.rootFolder, [vim.HostSystem], True
            ).view
            if h.name == hostname
        ),
        None,
    )
    if host_obj:
        if host_obj.inMaintenanceMode:
            task = host_obj.ExitMaintenanceMode_Task(timeout=0)
            task_result = task.info.state
    Disconnect(si)


def apply_firmware(
    host: Host,
    fw_path: str,
    dry_run: bool = False,
    attempts: int = 3,
    backoff: int = 30,
) -> str:
    """Apply firmware via Redfish with retry logic."""

    logger.info("Starting firmware update on %s (dry_run=%s)", host.hostname, dry_run)
    if dry_run:
        return "DRYRUN"

    attempt = 0
    status = "ERROR"
    while attempt < attempts:
        try:
            if host.vcenter:
                _enter_maintenance(host.hostname)

            rf = RedfishClient(
                base_url=f"https://{host.idrac_ip}",
                username=config.IDRAC_DEFAULT_USER,
                password=config.IDRAC_DEFAULT_PASS,
                default_prefix="/redfish/v1",
            )
            rf.login()
            response = rf.simple_update(fw_path)
            task_monitor = response.headers.get("Location")
            poll = 0
            while poll < 60:
                task_status = rf.get(task_monitor).dict
                if task_status.get("TaskState") in ("Completed", "Exception", "Killed"):
                    break
                time.sleep(30)
                poll += 1
            state = task_status.get("TaskState")
            rf.logout()
            status = "SUCCESS" if state == "Completed" else "FAILED"
            break
        except RequestException as exc:
            attempt += 1
            logger.warning(
                "Redfish attempt %s on %s failed: %s", attempt, host.hostname, exc
            )
            time.sleep(backoff * attempt)
        finally:
            try:
                if host.vcenter:
                    _exit_maintenance(host.hostname)
            except Exception as exc:
                logger.error("Maintenance exit failed on %s: %s", host.hostname, exc)
    return status
