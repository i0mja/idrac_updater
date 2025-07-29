"""
SPDX-License-Identifier: Apache-2.0
Authentication and first-time setup routes.
"""

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from models import LocalUser, db

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Log in using a local account."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = LocalUser.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session["username"] = username
            flash("Logged in successfully", "success")
            next_url = request.args.get("next") or url_for("ui.dashboard_page")
            return redirect(next_url)
        flash("Invalid credentials", "error")
    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """Clear session and return to login page."""
    session.pop("username", None)
    return redirect(url_for("auth.login"))


@auth_bp.route("/setup", methods=["GET", "POST"])
def first_setup():
    """Create the initial admin account."""
    if LocalUser.query.first():
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if not username or not password:
            flash("Username and password required", "error")
        elif password != confirm:
            flash("Passwords do not match", "error")
        else:
            user = LocalUser(
                username=username,
                password_hash=generate_password_hash(password),
                role="Admin",
            )
            db.session.add(user)
            db.session.commit()
            session["username"] = username
            flash("Admin account created", "success")
            return redirect(url_for("ui.dashboard_page"))
    return render_template("setup.html")
