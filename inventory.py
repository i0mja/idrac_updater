"""Inventory discovery for iDRAC and vCenter hosts"""

import yaml
import re
from datetime import datetime
from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect
import ssl
import config
from models import db, Host

def discover_idrac_from_list(idrac_list: list[dict]) -> None:
    """Insert or update Host entries based on provided list of dicts {hostname, idrac_ip}"""
    for item in idrac_list:
        host = Host.query.filter_by(hostname=item["hostname"]).first()
        if not host:
            host = Host(hostname=item["hostname"], idrac_ip=item["idrac_ip"])
        host.last_seen = datetime.utcnow()
        db.session.add(host)
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

    container = content.viewManager.CreateContainerView(content.rootFolder, [vim.HostSystem], True)
    for esxi in container.view:
        name = esxi.name
        idrac_ip = None
        for nic in esxi.config.network.vnic:
            if re.match(r"^idrac", nic.device):
                idrac_ip = nic.spec.ip.ipAddress
                break
        host = Host.query.filter_by(hostname=name).first()
        if not host:
            host = Host(hostname=name, idrac_ip=idrac_ip, vcenter=config.VCENTER_HOST, cluster=esxi.parent.name)
        host.idrac_ip = idrac_ip
        host.cluster = esxi.parent.name
        if policy_key:
            policy_val = esxi.value[policy_key] if policy_key < len(esxi.value) else None
            host.host_policy = policy_val
        host.last_seen = datetime.utcnow()
        db.session.add(host)
    db.session.commit()
    Disconnect(si)

import logging
from . import scheduler as scheduler_mod
from models import Schedule, Task, FirmwareRepo
import validators
import update

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
        ok = validators.validate_idrac_connection(host.idrac_ip, config.IDRAC_DEFAULT_USER, config.IDRAC_DEFAULT_PASS)
        host.last_status = "OK" if ok else "ERROR"
        host.last_message = "Health OK" if ok else "Unreachable"
        db.session.add(host)
    db.session.commit()


def perform_host_update(host_id: int, firmware_path: str, dry_run: bool, task_id: int | None = None):
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
        rf = RedfishClient(base_url=f"https://{ip}", username=config.IDRAC_DEFAULT_USER, password=config.IDRAC_DEFAULT_PASS)
        rf.login()
        data = rf.get("/redfish/v1/Systems/System.Embedded.1").dict
        rf.logout()
        return data
    except Exception:
        return {}


def load_schedules():
    scheduler_mod.load_schedules()


