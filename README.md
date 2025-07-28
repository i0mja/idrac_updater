# Firmware Maestro

Firmware Maestro is a minimal Flask application to orchestrate Dell iDRAC firmware updates.
It integrates with VMware vCenter for maintenance mode automation and supports Apache
SPNEGO/LDAP authentication on RHEL 9 systems joined to IdM with AD trusts.

## Quick start

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=app.py
flask shell -c "from models import db; db.create_all()"
flask run
```

For production, deploy under Apache using `wsgi.py` and `apache_firmware_maestro.conf`.
Edit `config.py` to adjust environment specific options.
