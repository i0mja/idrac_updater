"""iDrac Updater

README
======

iDrac Updater is a minimal web‑based firmware‑update orchestrator for Dell iDRAC endpoints.
It discovers hosts via Redfish and VMware vCenter, schedules updates with APScheduler,
and integrates with RHEL IdM/AD trusts using Apache SPNEGO/Kerberos SSO.

Quick start (RHEL 9)
--------------------

1. Ensure the RHEL host is IPA/IdM‑joined and trusts AD.
2. Install system packages:
       sudo dnf install httpd mod_ssl mod_auth_gssapi mod_authnz_ldap python3 python3‑pip gcc
3. Clone & install:
       git clone https://example.com/idrac_updater.git
       cd idrac_updater
       python3 -m venv venv
       source venv/bin/activate
       pip install -r requirements.txt
4. Adjust *config.py* (DB path, AD groups, SMTP, vCenter creds, etc.).
5. Initialize DB:
       export FLASK_APP=app.py
       flask shell -c "from models import db; db.create_all()"
6. Run stand‑alone for tests:
       flask run --debug
7. Deploy behind Apache using the supplied *apache_idrac_updater.conf* and *wsgi.py*.

For detailed docs see each file’s inline comments.

"""

import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from models import db, Host, Group, Schedule, VCenter
from scheduler import scheduler, load_schedules
import inventory
import utils
import validators
import config

# --- Flask setup ---
app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{config.DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
scheduler.init_app(app)

# --- Logging ---
handler = RotatingFileHandler(config.LOG_PATH, maxBytes=5*1024*1024, backupCount=3)
handler.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO, handlers=[handler])

# --- CLI commands ---
@app.cli.command("discover")
def discover():
    """CLI: manual discovery run"""
    inventory.discover_from_vcenter()
    utils.notify_console("Discovery complete")

# --- Routes ---
@app.route("/")
@utils.require_role("Viewer")
def dashboard():
    hosts = Host.query.limit(10).all()
    schedules = Schedule.query.limit(10).all()
    return render_template("dashboard.html", hosts=hosts, schedules=schedules)

@app.route("/hosts")
@utils.require_role("Viewer")
def hosts():
    hosts = Host.query.all()
    return render_template("hosts.html", hosts=hosts)

@app.route("/vcenters")
@utils.require_role("Viewer")
def vcenters():
    vcenters = VCenter.query.all()
    return render_template("vcenters.html", vcenters=vcenters)

@app.route("/vcenters/<int:vc_id>/test")
@utils.require_role("Operator")
def test_vcenter(vc_id):
    vc = VCenter.query.get_or_404(vc_id)
    ok = validators.validate_vcenter_connection(vc.url, vc.username, vc.password)
    flash("Connection OK" if ok else "Connection failed", "success" if ok else "error")
    return redirect(url_for('vcenters'))

@app.route("/hosts/<int:host_id>/policy", methods=["POST"])
@utils.require_role("Operator")
def update_policy(host_id):
    policy = request.form.get("policy")
    host = Host.query.get_or_404(host_id)
    host.host_policy = policy
    db.session.commit()
    flash("Policy updated", "success")
    return redirect(url_for("hosts"))

@app.route("/schedules", methods=["GET", "POST"])
@utils.require_role("Operator")
def schedules():
    if request.method == "POST":
        name = request.form["name"]
        firmware_path = request.form["firmware_path"]
        group_id = request.form.get("group_id")
        cron = request.form.get("cron")
        interval = request.form.get("interval")
        dry_run = bool(request.form.get("dry_run"))
        enabled = bool(request.form.get("enabled", True))
        sched = Schedule(name=name, firmware_path=firmware_path, cron=cron or None,
                         interval_minutes=int(interval) if interval else None,
                         target_group_id=int(group_id) if group_id else None,
                         dry_run=dry_run,
                         enabled=enabled)
        db.session.add(sched)
        db.session.commit()
        load_schedules()
        flash("Schedule saved", "success")
    groups = Group.query.all()
    schedules = Schedule.query.all()
    return render_template("schedules.html", schedules=schedules, groups=groups)

@app.route("/settings")
@utils.require_role("Admin")
def settings():
    return render_template("settings.html")

@app.route("/help")
@utils.require_role("Viewer")
def help():
    return render_template("help.html")

@app.route("/healthz")
def healthz():
    return "ok"

@app.route("/readiness")
def readiness():
    # simple readiness check of first records
    host = Host.query.first()
    vc = VCenter.query.first()
    if host and not validators.validate_idrac_connection(host.idrac_ip, config.IDRAC_DEFAULT_USER, config.IDRAC_DEFAULT_PASS):
        return "idrac fail", 500
    if vc and not validators.validate_vcenter_connection(vc.url, vc.username, vc.password):
        return "vcenter fail", 500
    return "ready"

def start_scheduler():
    load_schedules()
    scheduler.start()

try:
    app.before_first_request(start_scheduler)
except AttributeError:
    # fallback for very old Flask versions
    app.before_request(start_scheduler)

if __name__ == "__main__":
    app.run()
