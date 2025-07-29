"""Utility helpers: notifications, RBAC"""

import subprocess
import smtplib
from email.message import EmailMessage
import json
import requests
from functools import wraps
from flask import request, abort
import config

def get_user_groups(username: str) -> list[str]:
    """Return list of groups the user belongs to using system 'id -Gn' (SSSD cache)."""
    try:
        out = subprocess.check_output(["id", "-Gn", username], text=True)
        return out.strip().split()
    except subprocess.CalledProcessError:
        return []

def get_user_role(username: str) -> str:
    groups = get_user_groups(username)
    if config.ADMIN_GROUP in groups:
        return "Admin"
    if config.OPERATOR_GROUP in groups:
        return "Operator"
    return "Viewer"

def require_role(role: str):
    """Decorator to enforce min role"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            username = request.environ.get("REMOTE_USER") or request.headers.get("X-Remote-User")
            if not username:
                abort(401)
            roles = ["Viewer", "Operator", "Admin"]
            user_role = get_user_role(username)
            if roles.index(user_role) < roles.index(role):
                abort(403)
            request.user = username
            request.user_role = user_role
            return f(*args, **kwargs)
        return wrapped
    return decorator

# --- Notifications ---

def notify_console(msg: str):
    print(f"[NOTIFY] {msg}")

def notify_email(to_addrs: list[str], subject: str, body: str):
    message = EmailMessage()
    message["From"] = config.SMTP_FROM
    message["To"] = ", ".join(to_addrs)
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as smtp:
        smtp.send_message(message)

def notify_webhook(url: str, payload: dict):
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as exc:
        print(f"Webhook notify failed: {exc}")


# --- Helper functions ---

def allowed_file(filename: str, allowed_exts: set[str]) -> bool:
    """Check if filename has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {e.lower() for e in allowed_exts}


def check_database() -> bool:
    from models import db
    try:
        db.session.execute("SELECT 1")
        return True
    except Exception:
        return False


def check_sample_idrac() -> bool:
    from models import Host
    import validators
    host = Host.query.first()
    if not host:
        return True
    return validators.validate_idrac_connection(host.idrac_ip, config.IDRAC_DEFAULT_USER, config.IDRAC_DEFAULT_PASS)


def check_vcenters() -> bool:
    from models import VCenter
    import validators
    for vc in VCenter.query.all():
        if not validators.validate_vcenter_connection(vc.url, vc.username, vc.password):
            return False
    return True


def check_system_health() -> bool:
    return check_database() and check_vcenters()


def create_system_backup() -> str | None:
    """Very basic database backup."""
    import shutil
    from pathlib import Path
    import time
    src = Path(config.DB_PATH)
    if not src.exists():
        return None
    backup_dir = Path(config.BASE_DIR) / "backups"
    backup_dir.mkdir(exist_ok=True)
    target = backup_dir / f"backup_{int(time.time())}.db"
    try:
        shutil.copy(src, target)
        return str(target)
    except Exception:
        return None

