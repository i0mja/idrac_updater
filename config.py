"""Configuration loader for Firmware Maestro.

Values can be overridden with environment variables or a .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = os.getenv('FM_DB_PATH', str(BASE_DIR / 'firmware_maestro.sqlite'))
SECRET_KEY = os.getenv('FM_SECRET_KEY', 'change-me')

ADMIN_GROUP = os.getenv('FM_ADMIN_GROUP', 'FW_MAESTRO_ADMIN')
OPERATOR_GROUP = os.getenv('FM_OPERATOR_GROUP', 'FW_MAESTRO_OPERATOR')
VIEWER_GROUP = os.getenv('FM_VIEWER_GROUP', 'FW_MAESTRO_VIEWER')

DEFAULT_MAX_CONCURRENT_UPDATES = int(os.getenv('FM_MAX_CONCURRENT', '2'))
DEFAULT_MAINTENANCE_WINDOW = os.getenv('FM_MAINT_WINDOW', 'Sat 00:00-06:00')

SMTP_SERVER = os.getenv('FM_SMTP_SERVER', 'localhost')
SMTP_FROM = os.getenv('FM_SMTP_FROM', 'firmware-maestro@example.com')
SMTP_PORT = int(os.getenv('FM_SMTP_PORT', '25'))

VCENTER_USER = os.getenv('FM_VC_USER', 'administrator@vsphere.local')
VCENTER_PASS = os.getenv('FM_VC_PASS', 'changeme')
VCENTER_HOST = os.getenv('FM_VC_HOST', 'vcenter.example.com')

IDRAC_CRED_FILE = os.getenv('FM_IDRAC_CRED_FILE', str(BASE_DIR / 'idrac_creds.yaml'))

# Default credentials for newly discovered hosts
IDRAC_DEFAULT_USER = os.getenv('FM_IDRAC_USER', 'root')
IDRAC_DEFAULT_PASS = os.getenv('FM_IDRAC_PASS', 'calvin')

LOG_PATH = os.getenv('FM_LOG_PATH', str(BASE_DIR / 'fm.log'))
