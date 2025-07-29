"""Inventory discovery for iDRAC and vCenter hosts"""

import re
import ssl
from datetime import datetime
from typing import Optional

import yaml
from pyVim.connect import Disconnect, SmartConnect
from pyVmomi import vim
from sqlalchemy import or_

import config
from models import Host, db


def _upsert_host(
    hostname: str,
    idrac_ip: str,
    vcenter: Optional[str] = None,
    cluster: Optional[str] = None,
    host_policy: Optional[str] = None,
) -> Host:
    """Insert or update a host entry matching by hostname or iDRAC IP."""
    host = Host.query.filter(
        or_(Host.hostname == hostname, Host.idrac_ip == idrac_ip)
    ).first()
    if not host:
        host = Host(hostname=hostname, idrac_ip=idrac_ip)
    host.idrac_ip = idrac_ip
    if vcenter:
        host.vcenter = vcenter
    if cluster:
        host.cluster = cluster
    if host_policy is not None:
        host.host_policy = host_policy
    host.last_seen = datetime.utcnow()
    db.session.add(host)
    return host


def discover_idrac_from_list(idrac_list: list[dict]) -> None:
    """Insert or update host entries from a provided list."""
    for item in idrac_list:
        _upsert_host(item["hostname"], item["idrac_ip"])
    db.session.commit()


def discover_from_vcenter() -> None:
    """Connect to vCenter and map ESXi to iDRAC IP. Also sync HOST_POLICY tag."""
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
    custom_field_mgr = content.customFieldsManager

    policy_key = None
    for field in custom_field_mgr.field:
        if field.name == "HOST_POLICY":
            policy_key = field.key
            break

    container = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.HostSystem], True
    )
    for esxi in container.view:
        name = esxi.name
        idrac_ip = None
        for nic in esxi.config.network.vnic:
            if re.match(r"^idrac", nic.device):
                idrac_ip = nic.spec.ip.ipAddress
                break
        policy_val = None
        if policy_key:
            policy_val = (
                esxi.value[policy_key] if policy_key < len(esxi.value) else None
            )
        _upsert_host(
            name,
            idrac_ip,
            vcenter=config.VCENTER_HOST,
            cluster=esxi.parent.name,
            host_policy=policy_val,
        )
    db.session.commit()
    Disconnect(si)


import logging

import scheduler as scheduler_mod
import update
import validators
from models import FirmwareRepo, Schedule, Task

logger = logging.getLogger(__name__)


def discover_from_redfish():
    """Dummy discovery using credentials file."""
    try:
        with open(config.IDRAC_CRED_FILE) as f:
            hosts = yaml.safe_load(f) or []
    except FileNotFoundError:
        logger.warning("IDRAC_CRED_FILE not found")
        return
    if isinstance(hosts, list):
        discover_idrac_from_list(hosts)


def sync_firmware_repo():
    logger.info("Sync firmware repository stub")


def perform_health_checks():
    logger.info("Running basic health checks")
    for host in Host.query.all():
        ok = validators.validate_idrac_connection(
            host.idrac_ip, config.IDRAC_DEFAULT_USER, config.IDRAC_DEFAULT_PASS
        )
        host.last_status = "OK" if ok else "ERROR"
        host.last_message = "Health OK" if ok else "Unreachable"
        db.session.add(host)
    db.session.commit()


def perform_host_update(
    host_id: int, firmware_path: str, dry_run: bool, task_id: Optional[int] = None
):
    host = Host.query.get(host_id)
    if not host:
        return
    result = update.apply_firmware(host, firmware_path, dry_run)
    if task_id:
        task = Task.query.get(task_id)
        if task:
            task.status = result
            db.session.add(task)
    db.session.commit()


def get_host_inventory(ip: str) -> dict:
    try:
        from redfish_client import RedfishClient

        rf = RedfishClient(
            base_url=f"https://{ip}",
            username=config.IDRAC_DEFAULT_USER,
            password=config.IDRAC_DEFAULT_PASS,
        )
        rf.login()
        data = rf.get("/redfish/v1/Systems/System.Embedded.1").dict
        rf.logout()
        return data
    except Exception:
        return {}


def load_schedules():
    scheduler_mod.load_schedules()
