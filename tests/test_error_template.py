from pathlib import Path

import pytest
from flask import Flask, render_template

from blueprints.ui import ui_bp


@pytest.fixture
def app(tmp_path):
    root = Path(__file__).resolve().parents[1]
    app = Flask(
        __name__,
        template_folder=str(root / "templates"),
        static_folder=str(root / "static"),
    )
    app.register_blueprint(ui_bp)
    app.config["TESTING"] = True
    return app


def test_error_template_dashboard_link(app):
    with app.test_request_context():
        html = render_template("error.html", error_code=404, message="missing")
    assert 'href="/dashboard"' in html
