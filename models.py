"""SQLAlchemy models for iDrac Updater"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
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
    groups = db.relationship("Group", secondary="host_group_map", back_populates="hosts")

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
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String, default="RUNNING")  # RUNNING, SUCCESS, FAILED, PARTIAL
    message = db.Column(db.String, nullable=True)
    __table_args__ = (
        UniqueConstraint("schedule_id", "start_time", name="_schedule_start_uc"),
    )
