"""Firmware update logic via Redfish + vCenter maintenance mode"""

import time
import logging
from redfish_client import RedfishClient
from requests.exceptions import RequestException
from pyVim.connect import SmartConnect, Disconnect
import ssl
from pyVmomi import vim
from models import Host
import config

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
    host_obj = next((h for h in content.viewManager.CreateContainerView(content.rootFolder, [vim.HostSystem], True).view if h.name == hostname), None)
    if host_obj:
        if not host_obj.inMaintenanceMode:
            task = host_obj.EnterMaintenanceMode_Task(timeout=0)
            task_result = task.info.state
    Disconnect(si)

def _exit_maintenance(hostname: str):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    si = SmartConnect(host=config.VCENTER_HOST, user=config.VCENTER_USER, pwd=config.VCENTER_PASS, sslContext=ctx)
    content = si.RetrieveContent()
    host_obj = next((h for h in content.viewManager.CreateContainerView(content.rootFolder, [vim.HostSystem], True).view if h.name == hostname), None)
    if host_obj:
        if host_obj.inMaintenanceMode:
            task = host_obj.ExitMaintenanceMode_Task(timeout=0)
            task_result = task.info.state
    Disconnect(si)

def apply_firmware(host: Host, fw_path: str, dry_run: bool = False):
    """Return status string"""
    logger.info(f"Starting firmware update on {host.hostname} (dry_run={dry_run})")
    if dry_run:
        return "DRYRUN"
    # Enter maintenance for ESXi hosts
    if host.vcenter:
        _enter_maintenance(host.hostname)
    redfish_obj = RedfishClient(
        base_url=f"https://{host.idrac_ip}",
        username=config.IDRAC_DEFAULT_USER,
        password=config.IDRAC_DEFAULT_PASS,
        default_prefix="/redfish/v1",
    )
    try:
        redfish_obj.login()
        response = redfish_obj.simple_update(fw_path)
        task_monitor = response.headers.get("Location")
        retries = 0
        while retries < 60:
            task_status = redfish_obj.get(task_monitor).dict
            if task_status.get("TaskState") in ("Completed", "Exception", "Killed"):
                break
            time.sleep(30)
            retries += 1
        state = task_status.get("TaskState")
        if state == "Completed":
            status = "SUCCESS"
        else:
            if retries == 0:
                # retry once
                return apply_firmware(host, fw_path, dry_run)
            status = "FAILED"
    except RequestException as exc:
        logger.error(f"Redfish error on {host.hostname}: {exc}")
        status = "ERROR"
    finally:
        redfish_obj.logout()
        if host.vcenter:
            _exit_maintenance(host.hostname)
    return status
