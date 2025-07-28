"""Input validation helpers for iDrac Updater."""

import re
import smtplib
import requests
from urllib.parse import urlparse
from pyVim.connect import SmartConnect, Disconnect
import ssl


def validate_idrac_connection(ip: str, user: str, pwd: str) -> bool:
    """Return True if able to connect to iDRAC via Redfish."""
    from redfish_client import RedfishClient
    try:
        client = RedfishClient(base_url=f"https://{ip}", username=user, password=pwd)
        client.login()
        client.get('/redfish/v1/Systems')
        client.logout()
        return True
    except Exception:
        return False


def validate_vcenter_connection(url: str, user: str, pwd: str) -> bool:
    """Return True if we can login to vCenter."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        si = SmartConnect(host=urlparse(url).hostname, user=user, pwd=pwd, sslContext=ctx)
        Disconnect(si)
        return True
    except Exception:
        return False


def validate_cron_expression(expr: str) -> bool:
    """Very loose validation of cron expression m h dom mon dow."""
    return bool(re.fullmatch(r"[\d*/,-]+ [\d*/,-]+ [\d*/,-]+ [\d*/,-]+ [\d*/,-]+", expr))


def validate_smtp(server: str, port: int) -> bool:
    try:
        with smtplib.SMTP(server, port, timeout=5) as smtp:
            smtp.noop()
        return True
    except Exception:
        return False


def validate_webhook(url: str) -> bool:
    try:
        r = requests.head(url, timeout=5)
        return r.status_code < 400
    except Exception:
        return False
