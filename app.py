"""
iDrac Updater
================================
A comprehensive web-based firmware update orchestrator for Dell iDRAC endpoints.
Features include:
- Multi-source host discovery (Redfish, vCenter, manual)
- Advanced scheduling with APScheduler
- Kerberos SSO integration
- Firmware repository management
- Comprehensive logging and notifications
- Health checks and maintenance operations
"""

import logging
import os
import secrets
import subprocess
from datetime import datetime
from logging.handlers import RotatingFileHandler, SMTPHandler

from celery import Celery
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_apscheduler import APScheduler
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

import config
import crypto_utils
import inventory
import utils
import validators
from models import FirmwareRepo, Group, Host, Schedule, Task, User, VCenter, db

# --- Flask setup ---
app = Flask(__name__)
app.config.from_object(config)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{config.DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)


def make_celery(flask_app: Flask) -> Celery:
    celery = Celery(
        flask_app.import_name,
        broker=config.CELERY_BROKER_URL,
        backend=config.CELERY_RESULT_BACKEND,
    )
    celery.conf.update(flask_app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return super().__call__(*args, **kwargs)

    celery.Task = ContextTask
    return celery


celery = make_celery(app)

from scheduler import init_scheduler as init_sched
from scheduler import scheduler as scheduler_obj

scheduler = scheduler_obj
init_sched(app)

# --- Security Setup ---
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", secrets.token_urlsafe(64))


# --- Logging Configuration ---
def configure_logging():
    log_level = logging.DEBUG if app.config["DEBUG"] else logging.INFO

    # File logging
    file_handler = RotatingFileHandler(
        app.config["LOG_PATH"], maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB
    )
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        )
    )
    file_handler.setLevel(log_level)

    # Email logging for errors
    if app.config["MAIL_SERVER"]:
        mail_handler = SMTPHandler(
            mailhost=(app.config["MAIL_SERVER"], app.config["MAIL_PORT"]),
            fromaddr=app.config["MAIL_FROM"],
            toaddrs=app.config["ADMIN_EMAILS"],
            subject="iDrac Updater Failure",
            credentials=(app.config["MAIL_USERNAME"], app.config["MAIL_PASSWORD"]),
            secure=() if app.config["MAIL_USE_TLS"] else None,
        )
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)

    app.logger.addHandler(file_handler)
    app.logger.setLevel(log_level)
    app.logger.info("iDrac Updater starting...")


configure_logging()


# --- Template Filters ---
@app.template_filter("humanize")
def humanize_date(value):
    if not value:
        return ""
    return value.strftime("%Y-%m-%d %H:%M")


@app.template_filter("host_status")
def host_status_filter(status_code):
    status_map = {
        0: ("Offline", "secondary"),
        1: ("Online", "success"),
        2: ("Needs Attention", "warning"),
        3: ("Updating", "info"),
        4: ("Error", "danger"),
    }
    return status_map.get(status_code, ("Unknown", "dark"))


# --- Error Handlers ---
@app.errorhandler(401)
def unauthorized(e):
    if request.accept_mimetypes.accept_json:
        return jsonify(error="Unauthorized"), 401
    return render_template("error.html", error_code=401, message="Access denied"), 401


@app.errorhandler(404)
def not_found(e):
    return (
        render_template("error.html", error_code=404, message="Resource not found"),
        404,
    )


@app.errorhandler(500)
def server_error(e):
    return (
        render_template("error.html", error_code=500, message="Internal server error"),
        500,
    )


# --- CLI Commands ---
@app.cli.command("initdb")
def init_db():
    """Initialize the database"""
    db.create_all()
    app.logger.info("Database initialized")


@app.cli.command("discover")
def discover_hosts():
    """Run host discovery from all sources"""
    with app.app_context():
        inventory.discover_from_vcenter()
        inventory.discover_from_redfish()
        app.logger.info("Host discovery completed")


@app.cli.command("run-task")
def run_task():
    """Run a specific task by name"""
    task_name = input("Enter task name: ")
    if task_name == "firmware-sync":
        inventory.sync_firmware_repo()
    elif task_name == "health-check":
        inventory.perform_health_checks()
    else:
        app.logger.error(f"Unknown task: {task_name}")


# --- Context Processors ---
@app.context_processor
def inject_globals():
    return {
        "now": datetime.utcnow(),
        "app_version": config.VERSION,
        "debug_mode": app.config["DEBUG"],
    }


# --- Before Request Handlers ---
@app.before_request
def before_request():
    # Initialize session
    session.permanent = True
    app.permanent_session_lifetime = app.config["SESSION_LIFETIME"]

    # Set username from Kerberos if available
    if "username" not in session and request.headers.get("REMOTE_USER"):
        session["username"] = request.headers["REMOTE_USER"]

    # Log request for debugging
    if app.config["DEBUG"]:
        app.logger.debug(f"Request: {request.method} {request.path}")


# --- Main Routes ---
@app.route("/")
@utils.require_role("Viewer")
def dashboard():
    """System dashboard with overview information"""
    stats = {
        "hosts": Host.query.count(),
        "groups": Group.query.count(),
        "schedules": Schedule.query.count(),
        "pending_updates": Host.query.filter(Host.update_available == True).count(),
        "recent_tasks": Task.query.order_by(Task.created_at.desc()).limit(5).all(),
        "system_status": "OK" if utils.check_system_health() else "Degraded",
    }
    return render_template("dashboard.html", stats=stats)


@app.route("/hosts")
@utils.require_role("Viewer")
def host_list():
    """List all discovered hosts"""
    page = request.args.get("page", 1, type=int)
    per_page = 20
    hosts = Host.query.order_by(Host.last_seen.desc()).paginate(
        page, per_page, error_out=False
    )
    return render_template("hosts.html", hosts=hosts)


@app.route("/hosts/<int:host_id>")
@utils.require_role("Viewer")
def host_detail(host_id):
    """Host detail view with current status and history"""
    host = Host.query.get_or_404(host_id)
    tasks = (
        Task.query.filter_by(host_id=host_id)
        .order_by(Task.created_at.desc())
        .limit(10)
        .all()
    )
    return render_template("host_detail.html", host=host, tasks=tasks)


@app.route("/hosts/<int:host_id>/update", methods=["POST"])
@utils.require_role("Operator")
def update_host(host_id):
    """Manually trigger update for a host"""
    host = Host.query.get_or_404(host_id)
    firmware_path = request.form.get(
        "firmware_path", app.config["DEFAULT_FIRMWARE_PATH"]
    )
    dry_run = "dry_run" in request.form

    # Create task record
    task = Task(
        name=f"Manual update: {host.hostname}",
        description=f"Firmware: {firmware_path}",
        created_by=session.get("username", "system"),
        host_id=host.id,
    )
    db.session.add(task)
    db.session.commit()

    # Queue update job
    scheduler.add_job(
        func=inventory.perform_host_update,
        args=[host.id, firmware_path, dry_run, task.id],
        id=f"host_update_{host.id}_{task.id}",
        name=task.name,
    )

    flash(f"Update scheduled for {host.hostname} (Task #{task.id})", "success")
    return redirect(url_for("host_detail", host_id=host_id))


@app.route("/hosts/<int:host_id>/inventory")
@utils.require_role("Viewer")
def host_inventory(host_id):
    """Retrieve hardware inventory for host"""
    host = Host.query.get_or_404(host_id)
    inventory_data = inventory.get_host_inventory(host.idrac_ip)
    return render_template("host_inventory.html", host=host, inventory=inventory_data)


@app.route("/groups")
@utils.require_role("Viewer")
def group_list():
    """List all host groups"""
    groups = Group.query.all()
    return render_template("groups.html", groups=groups)


@app.route("/groups/create", methods=["GET", "POST"])
@utils.require_role("Admin")
def group_create():
    """Create a new host group"""
    if request.method == "POST":
        name = request.form["name"]
        description = request.form.get("description", "")
        query_filter = request.form["query_filter"]

        group = Group(name=name, description=description, query_filter=query_filter)
        db.session.add(group)
        db.session.commit()
        flash(f"Group '{name}' created", "success")
        return redirect(url_for("group_list"))
    return render_template("group_edit.html")


@app.route("/schedules")
@utils.require_role("Operator")
def schedule_list():
    """List all update schedules"""
    schedules = Schedule.query.order_by(Schedule.next_run_time.desc()).all()
    return render_template("schedules.html", schedules=schedules)


@app.route("/schedules/create", methods=["GET", "POST"])
@utils.require_role("Operator")
def schedule_create():
    """Create a new update schedule"""
    groups = Group.query.all()
    firmware_repos = FirmwareRepo.query.all()

    if request.method == "POST":
        # Validate and create schedule
        name = request.form["name"]
        firmware_path = request.form["firmware_path"]
        group_id = request.form.get("group_id")
        schedule_type = request.form["schedule_type"]
        cron_expr = request.form.get("cron_expression")
        interval = request.form.get("interval_minutes")
        start_date = request.form.get("start_date")
        enabled = "enabled" in request.form
        dry_run = "dry_run" in request.form

        # Create schedule object
        schedule = Schedule(
            name=name,
            firmware_path=firmware_path,
            target_group_id=group_id if group_id else None,
            schedule_type=schedule_type,
            cron_expression=cron_expr,
            interval_minutes=interval,
            start_date=(
                datetime.strptime(start_date, "%Y-%m-%dT%H:%M") if start_date else None
            ),
            enabled=enabled,
            dry_run=dry_run,
        )

        db.session.add(schedule)
        db.session.commit()
        inventory.load_schedules()

        flash(f"Schedule '{name}' created", "success")
        return redirect(url_for("schedule_list"))

    return render_template(
        "schedule_edit.html", groups=groups, firmware_repos=firmware_repos
    )


@app.route("/schedules/<int:schedule_id>/toggle", methods=["POST"])
@utils.require_role("Operator")
def toggle_schedule(schedule_id):
    """Enable/disable a schedule"""
    schedule = Schedule.query.get_or_404(schedule_id)
    schedule.enabled = not schedule.enabled
    db.session.commit()
    inventory.load_schedules()

    status = "enabled" if schedule.enabled else "disabled"
    flash(f"Schedule '{schedule.name}' {status}", "success")
    return redirect(url_for("schedule_list"))


@app.route("/firmware")
@utils.require_role("Viewer")
def firmware_list():
    """List available firmware repositories"""
    repos = FirmwareRepo.query.all()
    return render_template("firmware.html", repos=repos)


@app.route("/firmware/upload", methods=["POST"])
@utils.require_role("Admin")
def firmware_upload():
    """Upload new firmware package"""
    if "firmware_file" not in request.files:
        flash("No file selected", "error")
        return redirect(url_for("firmware_list"))

    file = request.files["firmware_file"]
    if file.filename == "":
        flash("No file selected", "error")
        return redirect(url_for("firmware_list"))

    if file and utils.allowed_file(
        file.filename, app.config["ALLOWED_FIRMWARE_EXTENSIONS"]
    ):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["FIRMWARE_UPLOAD_DIR"], filename)
        file.save(file_path)

        # Add to repository
        repo = FirmwareRepo(
            filename=filename,
            file_path=file_path,
            version=request.form.get("version"),
            model_compatibility=request.form.get("models"),
            uploader=session.get("username", "system"),
        )
        db.session.add(repo)
        db.session.commit()

        flash(f"Firmware '{filename}' uploaded successfully", "success")
    else:
        flash("Invalid file type", "error")

    return redirect(url_for("firmware_list"))


@app.route("/tasks")
@utils.require_role("Operator")
def task_list():
    """List all system tasks"""
    status_filter = request.args.get("status", "all")
    query = Task.query.order_by(Task.created_at.desc())

    if status_filter != "all":
        query = query.filter_by(status=status_filter)

    page = request.args.get("page", 1, type=int)
    per_page = 25
    tasks = query.paginate(page, per_page, error_out=False)
    return render_template("tasks.html", tasks=tasks, status_filter=status_filter)


@app.route("/tasks/<int:task_id>")
@utils.require_role("Operator")
def task_detail(task_id):
    """Task detail view with logs"""
    task = Task.query.get_or_404(task_id)
    log_path = os.path.join(app.config["TASK_LOG_DIR"], f"task_{task_id}.log")
    log_content = []

    if os.path.exists(log_path):
        with open(log_path, "r") as log_file:
            log_content = log_file.readlines()

    return render_template("task_detail.html", task=task, log_content=log_content)


@app.route("/vcenters")
@utils.require_role("Admin")
def vcenter_list():
    """List configured vCenter servers"""
    vcenters = VCenter.query.all()
    return render_template("vcenters.html", vcenters=vcenters)


@app.route("/vcenters/create", methods=["GET", "POST"])
@utils.require_role("Admin")
def vcenter_create():
    """Add a new vCenter server"""
    if request.method == "POST":
        name = request.form["name"]
        url = request.form["url"]
        username = request.form["username"]
        password = request.form["password"]
        enabled = "enabled" in request.form

        # Encrypt password before storage
        encrypted_password = crypto_utils.encrypt_data(
            password, app.config["SECRET_KEY"]
        )

        vcenter = VCenter(
            name=name,
            url=url,
            username=username,
            password=encrypted_password,
            enabled=enabled,
        )

        db.session.add(vcenter)
        db.session.commit()

        flash(f"vCenter '{name}' added", "success")
        return redirect(url_for("vcenter_list"))

    return render_template("vcenter_edit.html")


@app.route("/vcenters/<int:vc_id>/test")
@utils.require_role("Admin")
def test_vcenter(vc_id):
    """Test vCenter connection"""
    vc = VCenter.query.get_or_404(vc_id)

    # Decrypt password for connection test
    decrypted_password = crypto_utils.decrypt_data(
        vc.password, app.config["SECRET_KEY"]
    )

    success = validators.validate_vcenter_connection(
        vc.url, vc.username, decrypted_password
    )

    if success:
        flash("Connection successful", "success")
    else:
        flash("Connection failed", "error")

    return redirect(url_for("vcenter_list"))


@app.route("/settings", methods=["GET", "POST"])
@utils.require_role("Admin")
def system_settings():
    """System configuration settings"""
    if request.method == "POST":
        # Update configuration settings
        app.config["MAIL_NOTIFICATIONS"] = "mail_notifications" in request.form
        app.config["AUTO_DISCOVERY"] = "auto_discovery" in request.form
        app.config["DISCOVERY_INTERVAL"] = int(request.form["discovery_interval"])

        # Save to persistent storage if needed
        # ...

        flash("Settings updated", "success")
        return redirect(url_for("system_settings"))

    return render_template("settings.html")


@app.route("/help")
@utils.require_role("Viewer")
def help_page():
    """Display help documentation"""
    return render_template("help.html")


# --- API Endpoints ---
@app.route("/api/v1/hosts")
@utils.require_role("Viewer", api=True)
def api_host_list():
    """API endpoint for host listing"""
    hosts = Host.query.all()
    return jsonify(
        [
            {
                "id": h.id,
                "hostname": h.hostname,
                "ip": h.idrac_ip,
                "cluster": h.cluster,
                "host_policy": h.host_policy,
                "status": h.last_status,
                "last_seen": h.last_seen.isoformat() if h.last_seen else None,
            }
            for h in hosts
        ]
    )


@app.route("/api/v1/hosts/<int:host_id>/update", methods=["POST"])
@utils.require_role("Operator", api=True)
def api_update_host(host_id):
    """API endpoint to trigger host update"""
    host = Host.query.get_or_404(host_id)
    firmware_path = request.json.get(
        "firmware_path", app.config.get("DEFAULT_FIRMWARE_PATH")
    )
    dry_run = bool(request.json.get("dry_run", False))
    task = Task(
        name=f"API update: {host.hostname}",
        description=f"Firmware: {firmware_path}",
        created_by=session.get("username", "api"),
        host_id=host.id,
    )
    db.session.add(task)
    db.session.commit()
    scheduler.add_job(
        func=inventory.perform_host_update,
        args=[host.id, firmware_path, dry_run, task.id],
        id=f"host_update_{host.id}_{task.id}",
        name=task.name,
    )
    return jsonify({"status": "queued", "task_id": task.id})


@app.route("/api/v1/firmware_images")
@utils.require_role("Viewer", api=True)
def api_firmware_images():
    """Return available firmware packages."""
    repos = FirmwareRepo.query.all()
    return jsonify(
        [{"id": r.id, "filename": r.filename, "version": r.version} for r in repos]
    )


@app.route("/api/v1/tasks/<int:task_id>")
@utils.require_role("Viewer", api=True)
def api_task_status(task_id):
    """Return the status of a task."""
    task = Task.query.get_or_404(task_id)
    return jsonify(
        {
            "id": task.id,
            "status": task.status,
            "host_id": task.host_id,
            "created_at": task.created_at.isoformat(),
        }
    )


@app.route("/api/v1/update_job", methods=["POST"])
@utils.require_role("Operator", api=True)
def api_update_job():
    """Create update tasks for multiple hosts."""
    data = request.get_json() or {}
    host_ids = data.get("host_ids", [])
    firmware_path = data.get("firmware_path", app.config.get("DEFAULT_FIRMWARE_PATH"))
    dry_run = bool(data.get("dry_run", False))
    if not host_ids:
        return jsonify({"error": "host_ids required"}), 400
    task_ids = []
    for hid in host_ids:
        host = Host.query.get(hid)
        if not host:
            continue
        task = Task(
            name=f"API update: {host.hostname}",
            description=f"Firmware: {firmware_path}",
            created_by=session.get("username", "api"),
            host_id=host.id,
        )
        db.session.add(task)
        db.session.commit()
        scheduler.add_job(
            func=inventory.perform_host_update,
            args=[host.id, firmware_path, dry_run, task.id],
            id=f"host_update_{host.id}_{task.id}",
            name=task.name,
        )
        task_ids.append(task.id)
    return jsonify({"task_ids": task_ids})


# --- System Management Routes ---
@app.route("/system/maintenance")
@utils.require_role("Admin")
def system_maintenance():
    """System maintenance operations"""
    return render_template("maintenance.html")


@app.route("/system/restart", methods=["POST"])
@utils.require_role("Admin")
def system_restart():
    """Restart application (for updates)"""
    # In production, this would trigger a restart via process manager
    flash("Application restart initiated", "info")
    return redirect(url_for("system_maintenance"))


@app.route("/system/backup", methods=["POST"])
@utils.require_role("Admin")
def system_backup():
    """Create system backup"""
    backup_file = utils.create_system_backup()
    if backup_file:
        flash(f"Backup created: {backup_file}", "success")
    else:
        flash("Backup failed", "error")
    return redirect(url_for("system_maintenance"))


# --- Health Checks ---
@app.route("/healthz")
def health_check():
    """Basic health check endpoint"""
    try:
        db.session.execute("SELECT 1")
        return "OK", 200
    except Exception as e:
        app.logger.error(f"Health check failed: {str(e)}")
        return "Database connection failed", 500


@app.route("/readiness")
def readiness_check():
    """Comprehensive readiness check"""
    checks = {
        "database": utils.check_database(),
        "idrac_connectivity": utils.check_sample_idrac(),
        "vcenter_connectivity": utils.check_vcenters(),
        "task_queue": scheduler.running,
    }

    if all(checks.values()):
        return "READY", 200

    failed = [name for name, status in checks.items() if not status]
    return f"NOT READY: {', '.join(failed)}", 500


# --- Scheduler Initialization ---
def init_scheduler():
    """Add application periodic jobs to the scheduler."""
    if app.config["AUTO_DISCOVERY"]:
        scheduler.add_job(
            func=inventory.discover_from_vcenter,
            trigger="interval",
            minutes=app.config["DISCOVERY_INTERVAL"],
            id="auto_discovery",
            name="Automatic Host Discovery",
        )

    scheduler.add_job(
        func=inventory.perform_health_checks,
        trigger="cron",
        hour="2",
        id="daily_health_checks",
        name="Daily Health Checks",
    )

    scheduler.add_job(
        func=inventory.sync_firmware_repo,
        trigger="cron",
        day_of_week="mon",
        hour="3",
        id="firmware_sync",
        name="Weekly Firmware Sync",
    )

    app.logger.info("Scheduler initialized with %d jobs", len(scheduler.get_jobs()))


# Initialize scheduler when app starts
with app.app_context():
    init_scheduler()

# --- Entry Point ---
if __name__ == "__main__":
    # For development only
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])
