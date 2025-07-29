"""SQLAlchemy models for iDrac Updater"""

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()


class Host(db.Model):
    __tablename__ = "hosts"
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String, nullable=False, unique=True)
    idrac_ip = db.Column(db.String, nullable=False)
    vcenter = db.Column(db.String, nullable=True)
    cluster = db.Column(db.String, nullable=True)
    host_policy = db.Column(db.String, nullable=True)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_status = db.Column(db.String, default="UNKNOWN")  # OK, ERROR, UPDATING
    last_message = db.Column(db.String, nullable=True)
    groups = db.relationship(
        "Group", secondary="host_group_map", back_populates="hosts"
    )


class Group(db.Model):
    __tablename__ = "groups"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    dynamic_query = db.Column(db.String, nullable=True)  # For dynamic groups
    hosts = db.relationship("Host", secondary="host_group_map", back_populates="groups")


class HostGroupMap(db.Model):
    __tablename__ = "host_group_map"
    host_id = db.Column(db.Integer, db.ForeignKey("hosts.id"), primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), primary_key=True)


class VCenter(db.Model):
    __tablename__ = "vcenters"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False, unique=True)
    url = db.Column(db.String, nullable=False)
    username = db.Column(db.String, nullable=False)
    password = db.Column(db.String, nullable=False)


class Schedule(db.Model):
    __tablename__ = "schedules"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    cron = db.Column(db.String, nullable=True)
    interval_minutes = db.Column(db.Integer, nullable=True)
    enabled = db.Column(db.Boolean, default=True)
    target_group_id = db.Column(db.Integer, db.ForeignKey("groups.id"))
    target_group = db.relationship("Group")
    firmware_path = db.Column(db.String, nullable=False)
    dry_run = db.Column(db.Boolean, default=False)
    max_concurrent = db.Column(db.Integer, nullable=True)


class JobHistory(db.Model):
    __tablename__ = "job_history"
    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedules.id"))
    schedule = db.relationship("Schedule")
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(
        db.String, default="RUNNING"
    )  # RUNNING, SUCCESS, FAILED, PARTIAL
    message = db.Column(db.String, nullable=True)
    __table_args__ = (
        UniqueConstraint("schedule_id", "start_time", name="_schedule_start_uc"),
    )


class FirmwareRepo(db.Model):
    """Stored firmware packages"""

    __tablename__ = "firmware_repo"
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String, nullable=False)
    file_path = db.Column(db.String, nullable=False)
    version = db.Column(db.String)
    model_compatibility = db.Column(db.String)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploader = db.Column(db.String)


class Task(db.Model):
    """Background tasks such as manual updates"""

    __tablename__ = "tasks"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String)
    host_id = db.Column(db.Integer, db.ForeignKey("hosts.id"))
    host = db.relationship("Host")
    status = db.Column(db.String, default="QUEUED")


class User(db.Model):
    """Minimal user representation for audit records"""

    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, unique=True, nullable=False)
    role = db.Column(db.String, default="Viewer")


class LocalUser(db.Model):
    """Local application user for environments without SSO."""

    __tablename__ = "local_users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, unique=True, nullable=False)
    password_hash = db.Column(db.String, nullable=False)
    role = db.Column(db.String, default="Admin")
