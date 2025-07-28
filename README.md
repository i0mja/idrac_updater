# Firmware Maestro

**Firmware Maestro** is a simple yet powerful web-based firmware update orchestrator for Dell iDRAC endpoints. It discovers servers via Redfish and VMware vCenter, schedules updates using APScheduler, and integrates seamlessly with Red Hat IdM and Active Directory via Apache SPNEGO/Kerberos SSO.

---

## ✨ Features

- 🔐 Integrated authentication via SPNEGO/Kerberos and LDAP (SSSD, AD trusts)
- 🌐 Auto-discovers Dell iDRACs via Redfish and ESXi hosts from vCenter
- ♻️ Two-way sync of `HOST_POLICY` vCenter custom attribute for grouping/scheduling
- 🗓️ Flexible scheduling engine using APScheduler (cron and interval support)
- 🧑‍💼 Role-based access control (Admin / Operator / Viewer) via AD groups
- 🧪 Built-in vCenter and iDRAC connectivity validation
- 📋 Web dashboard for firmware job management, host inventory, and status

---

## 🚀 Quick Start (RHEL 9)

### 1. Prerequisites

Ensure your system:

- Is joined to **Red Hat IdM** and trusts your **Active Directory**
- Has internet access for Python dependencies or mirrors configured
- Has proper DNS/Kerberos configuration for SSO

Install system packages:

```bash
sudo dnf install httpd mod_ssl mod_auth_gssapi mod_authnz_ldap python3 python3-pip gcc
```

---

### 2. Clone and Set Up

```bash
git clone https://github.com/i0mja/idrac_updater.git 
cd idrac_updater
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

### 3. Configure

Edit `config.py`:

```python
DB_PATH = "/var/lib/idrac-updater/app.db"
LOG_PATH = "/var/log/idrac-updater/app.log"
VCENTER_HOST_POLICY_ATTRIBUTE = "HOST_POLICY"

# Secret key for Flask sessions
SECRET_KEY = "changeme"

# AD group mappings for RBAC
AD_GROUPS = {
    "Admin": "CN=FW_Admins,OU=Groups,DC=example,DC=com",
    "Operator": "CN=FW_Ops,OU=Groups,DC=example,DC=com",
    "Viewer": "CN=FW_Viewers,OU=Groups,DC=example,DC=com"
}

# SMTP/email notification settings (optional)
SMTP_SERVER = "mail.example.com"
SMTP_SENDER = "noreply@example.com"

# vCenter credentials (or use secrets manager)
VCENTER_CREDENTIALS = {
    "vcenter01.example.com": {
        "username": "administrator@vsphere.local",
        "password": "changeme"
    }
}
```

---

### 4. Initialize the Database

```bash
export FLASK_APP=app.py
flask shell -c "from models import db; db.create_all()"
```

---

### 5. Run in Development Mode

```bash
flask run --debug
```

---

### 6. Deploy Behind Apache (Production)

Configure Apache using the provided `apache_firmware_maestro.conf`:

```bash
cp apache_firmware_maestro.conf /etc/httpd/conf.d/
cp wsgi.py /var/www/idrac-updater/
```

Ensure the correct SELinux context and file permissions.

Then enable and restart Apache:

```bash
sudo systemctl enable --now httpd
```

Access the web interface at:\
`https://<your-server>/firmware`

---

## 🧐 CLI Utilities

Run host discovery manually:

```bash
flask discover
```

---

## ✅ Health Checks

| Endpoint     | Purpose                     |
| ------------ | --------------------------- |
| `/healthz`   | Basic HTTP 200 test         |
| `/readiness` | Tests iDRAC + vCenter reach |

---

## 📂 File Structure

| File/Dir                       | Purpose                             |
| ------------------------------ | ----------------------------------- |
| `app.py`                       | Main Flask app                      |
| `models.py`                    | SQLAlchemy DB models                |
| `scheduler.py`                 | APScheduler integration             |
| `utils.py`                     | Helper functions & decorators       |
| `validators.py`                | Connection checks for iDRAC/vCenter |
| `config.py`                    | User config                         |
| `templates/`                   | Jinja2 HTML templates               |
| `static/`                      | JS/CSS assets                       |
| `wsgi.py`                      | WSGI entrypoint for Apache          |
| `apache_firmware_maestro.conf` | Apache vhost config                 |

---

## 🔐 Authentication & Roles

Users authenticate via Kerberos (SPNEGO) if available, falling back to LDAP-based login using `mod_authnz_ldap`.

Roles are defined in `config.py` and mapped to AD groups:

- **Admin**: Full access to settings and job control
- **Operator**: Create/edit schedules, test connections
- **Viewer**: View dashboards, logs, host states

---

## 📬 Support & Contributing

For feature requests or bug reports, open an issue or pull request on the [GitHub repository](https://github.com/i0mja/idrac_updater).

---

## 📝 License

MIT License. See `LICENSE` file for details.

