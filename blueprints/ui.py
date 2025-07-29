"""
SPDX-License-Identifier: Apache-2.0
"""

from flask import Blueprint, render_template

import config
from utils import login_required

ui_bp = Blueprint("ui", __name__)


@ui_bp.route("/dashboard")
@login_required
def dashboard_page():
    return render_template("dashboard.html")


@ui_bp.route("/hosts")
@login_required
def hosts_page():
    return render_template("hosts.html")


@ui_bp.route("/jobs")
@login_required
def jobs_page():
    return render_template("jobs.html")


@ui_bp.route("/schedules")
@login_required
def schedules_page():
    return render_template("schedules.html")


@ui_bp.route("/firmware")
@login_required
def firmware_page():
    return render_template("firmware.html")


if config.VCENTER_HOST:

    @ui_bp.route("/vcenter")
    @login_required
    def vcenter_page():
        return render_template("vcenter.html")
