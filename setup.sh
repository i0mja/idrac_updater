#!/usr/bin/env bash
set -e

# create virtual environment
if [ ! -d venv ]; then
    python3 -m venv venv
fi
source venv/bin/activate

pip install -r requirements.txt

# initialise database
export FLASK_APP=app.py
flask shell <<'PY'
from app import app
from models import db
with app.app_context():
    db.create_all()
PY

echo "Environment ready. Activate with 'source venv/bin/activate'"
