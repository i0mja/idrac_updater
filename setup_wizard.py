import os
from pathlib import Path
import getpass


def prompt(question: str, default: str = None, secret: bool = False) -> str:
    if default:
        prompt_text = f"{question} [{default}]: "
    else:
        prompt_text = f"{question}: "
    if secret:
        value = getpass.getpass(prompt_text)
    else:
        value = input(prompt_text)
    return value.strip() or default or ""


def main():
    print("=== Firmware Maestro Setup Wizard ===")
    base_dir = Path(__file__).resolve().parent
    db_path = prompt("Database path", str(base_dir / "firmware_maestro.sqlite"))
    secret_key = prompt("Flask secret key", "change-me")
    admin_group = prompt("Admin group", "FW_MAESTRO_ADMIN")
    operator_group = prompt("Operator group", "FW_MAESTRO_OPERATOR")
    viewer_group = prompt("Viewer group", "FW_MAESTRO_VIEWER")
    smtp_server = prompt("SMTP server", "localhost")
    smtp_from = prompt("Email from address", "firmware-maestro@example.com")
    smtp_port = prompt("SMTP port", "25")
    vc_host = prompt("vCenter URL", "https://vcenter.example.com")
    vc_user = prompt("vCenter username", "administrator@vsphere.local")
    vc_pass = prompt("vCenter password", secret=True)
    idrac_user = prompt("Default iDRAC username", "root")
    idrac_pass = prompt("Default iDRAC password", "calvin", secret=True)
    idrac_file = prompt("iDRAC credential file", str(base_dir / "idrac_creds.yml"))
    log_path = prompt("Log file path", str(base_dir / "fm.log"))

    env_lines = [
        f"FM_DB_PATH={db_path}",
        f"FM_SECRET_KEY={secret_key}",
        f"FM_ADMIN_GROUP={admin_group}",
        f"FM_OPERATOR_GROUP={operator_group}",
        f"FM_VIEWER_GROUP={viewer_group}",
        f"FM_SMTP_SERVER={smtp_server}",
        f"FM_SMTP_FROM={smtp_from}",
        f"FM_SMTP_PORT={smtp_port}",
        f"FM_VC_HOST={vc_host}",
        f"FM_VC_USER={vc_user}",
        f"FM_VC_PASS={vc_pass}",
        f"FM_IDRAC_CRED_FILE={idrac_file}",
        f"FM_IDRAC_USER={idrac_user}",
        f"FM_IDRAC_PASS={idrac_pass}",
        f"FM_LOG_PATH={log_path}",
    ]

    with open(".env", "w") as f:
        f.write("\n".join(env_lines))
    print("Configuration saved to .env")

    for line in env_lines:
        key, val = line.split("=", 1)
        os.environ[key] = val

    vc_test_url = vc_host if vc_host.startswith('http') else f'https://{vc_host}'
    print("Testing vCenter connection...")
    try:
        import validators
        if validators.validate_vcenter_connection(vc_test_url, vc_user, vc_pass):
            print("vCenter connection successful.")
        else:
            print("WARNING: Could not connect to vCenter.")
    except Exception as exc:
        print(f"vCenter connection test failed: {exc}")

    from flask import Flask
    from models import db

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()
    print(f"Database initialised at {db_path}")
    print("Setup complete. Run 'flask run' to start the server.")


if __name__ == "__main__":
    main()
