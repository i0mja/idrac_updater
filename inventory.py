"""Inventory discovery for iDRAC and vCenter hosts"""

import yaml
import re
from datetime import datetime
from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect
import ssl
import config
from models import db, Host
from redfish import RedfishClient

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
