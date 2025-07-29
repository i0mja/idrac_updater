# AGENTS.md — Guidance for Humans & AI Agents

*(Scope: entire repository; nested **`AGENTS.md`** files take precedence if added later.)*

---

## 1  Project at a Glance

| Area              | Path(s)                                              | Notes                                             |
| ----------------- | ---------------------------------------------------- | ------------------------------------------------- |
| Flask entry‑point | `app.py`                                             | Web UI, REST, background scheduler bootstrap      |
| Models & ORM      | `models.py`                                          | SQLAlchemy, Alembic migrations via `flask db *`   |
| Discovery         | `inventory.py`, `redfish_client.py`                  | vCenter & Redfish helpers                         |
| Firmware Engine   | `update.py`                                          | Idempotent, retry‑aware upload & apply logic      |
| Scheduler         | `scheduler.py`                                       | APScheduler cron/interval jobs                    |
| CLI / Setup       | `init_db.py`, `utils.py`, `validators.py`            | `.env` bootstrap & sanity checks                  |
| Front‑end         | `templates/*`, `static/*`                            | Jinja2 + vanilla JS/CSS                           |
| Service files     | `apache_idrac_updater.conf`, `idrac_updater.service` | Apache vhost (Kerberos SSO) & systemd alternative |

---

## 2  Coding Conventions

| Tool           | Version Pin              | Invocation                   |
| -------------- | ------------------------ | ---------------------------- |
| **Python**     | 3.11 (RHEL 9 SCL)        | —                            |
| **Black**      | 24.x, `line‑length = 88` | `black .`                    |
| **isort**      | 5.x, profile =`black`    | `isort .`                    |
| **Flake8**     | 7.x                      | `flake8`                     |
| **Mypy**       | 1.10 (soft fail)         | `mypy .`                     |
| **Pre‑commit** | 3.x                      | `pre‑commit run --all-files` |

- Docstrings → Google‑style
- Use **type hints** everywhere; treat `mypy` warnings as TODOs.
- Avoid circular imports—split utility code into `utils.py` or a new module if needed.
- **No print debugging**; use `logging.getLogger("firmware_maestro")`.

### Imports

```python
# ✅ good
from inventory import discover_vcenter
from models import Host, Schedule

# ❌ bad
import inventory
from models import *
```

---

## 3  Branch & PR Guidelines

1. **Branch naming**:\
   `feat/<short‑slug>`, `fix/<issue‑ref>`, `chore/<task>`, `docs/<area>`.
2. **PR title** → imperative, ≤ 72 chars.\
   Examples: `feat: add OAuth2 fallback for local users`
3. **PR description template** (fill in all sections):
   ```
   ## What & Why
   <concise context and motivation>

   ## Changes
   - Bullet
   - Point

   ## How to test
   1. ...
   2. ...

   ## Screenshots / Logs
   <optional>

   ## Risks & Mitigations
   <optional>

   Closes #<issue>, Related #<issue>
   ```
4. **Status checks** must pass: `lint`, `unit`, `integration` (see `.github/workflows/ci.yml`).
5. **Commit messages** must be DCO‑signed: `git commit -s -m "..."`.

---

## 4  Environment Variables

| Variable            | Default                 | Description                                         |
| ------------------- | ----------------------- | --------------------------------------------------- |
| `FLASK_ENV`         | `production`            | `production`, `development`, or `testing`           |
| `FM_SECRET_KEY`     | *required*              | Flask session & CSRF secret                         |
| `DATABASE_URL`      | `sqlite:///data/app.db` | SQLAlchemy connection string                        |
| `FIRMWARE_REPO_DIR` | `/firmware`             | Mounted volume with `.d7` or `.exe` images          |
| `VCENTER_HOST`      | —                       | Optional vCenter for discovery                      |
| `LOG_LEVEL`         | `INFO`                  | Python logging level                                |
| `ENABLE_METRICS`    | `false`                 | If `true`, exposes Prometheus metrics on `/metrics` |
| `TRACING_ENDPOINT`  | —                       | OpenTelemetry collector URL                         |

All env vars are loaded via [`python-dotenv`](https://pypi.org/project/python-dotenv/). Secrets **must not** be committed to Git.

---

## 5  Testing & Validation

| Layer       | Framework            | Command                        |
| ----------- | -------------------- | ------------------------------ |
| Unit        | **pytest** 8.x       | `pytest -q`                    |
| Coverage    | pytest‑cov ≥ 90 %    | `pytest --cov=idrac_updater`   |
| Integration | marker `integration` | Requires vCenter/iDRAC testbed |
| Static      | pre‑commit linters   | `pre-commit run --all-files`   |

> **Programmatic check**
>
> ```bash
> ./scripts/checks.sh
> ```
>
> Script returns non‑zero on any failure (lint, type‑check, tests). **Run before pushing**.

---

## 6  Running Locally

```bash
# 1. Create env\python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env          # edit values or run python init_db.py --wizard
flask db upgrade              # creates SQLite DB if absent

# 3. Launch (development)
flask --app app run --reload
```

### Container Build & Release

Build is automated via **Podman** + **GitHub Actions**.

*Local build/test*

```bash
podman build -t idrac_updater:dev .
podman run --rm -p 8080:8080 --env-file .env idrac_updater:dev
```

*Release pipeline*

1. Tag commit `vX.Y.Z` (SemVer).
2. GitHub Action publishes to `quay.io/idrac_updater`.
3. SBOM + image provenance signed via **cosign**.

---

## 7  Database & Migrations

- ORM: **SQLAlchemy**; use `db.Model`.
- Migrations: **Flask‑Migrate/Alembic**.

Create a revision:

```bash
flask db migrate -m "Describe change"
flask db upgrade
```

---

## 8  Logging & Observability

- Logs: configured via `logging_config.py`; daily rotation, keep 14 files.
- Metrics: optional Prometheus exporter (enable with `ENABLE_METRICS=true`).
- Tracing: OpenTelemetry ([https://opentelemetry.io/](https://opentelemetry.io/)) if `TRACING_ENDPOINT` set.
- Sensitive data **must be redacted** before logging.

---

## 9  Security Hardening Checklist

-

---

## 10  Contributing Workflow

1. **Fork & clone** or create a feature branch if you are a maintainer.
2. **Run checks** locally (`./scripts/checks.sh`).
3. **Open PR** against `main`.
4. A maintainer will **review** within 2 business days.
5. **Squash‑merge** preferred; maintainers may re‑title commits.
6. After merge, **GitHub Actions** deploys `edge` container.

---

## 11  Support & Maintenance

| Channel                        | Usage                         | SLA           |
| ------------------------------ | ----------------------------- | ------------- |
| GitHub Issues                  | Bug reports, feature requests | Triage < 24 h |
| IRC `#idrac-updater`           | Quick questions               | Best‑effort   |
| PagerDuty “iDrac‑Updater‑Prod” | Production alerts only        | 15 min        |

Weekly on Monday 09:00 UTC we run **dependency updates** via Renovate.

---

## 12  FAQ

---

## 13  License

```
SPDX‑License‑Identifier: Apache‑2.0
```

Unless stated otherwise, all new files should include the SPDX line above at the top or in the module docstring.

---

## 14  Contact & Ownership

- **Code owners**: `@i0mja`, `@redhat‑firmware‑maestro`
- Preferred chat: IRC Libera `#idrac-updater` or Slack `@FW‑Maestro`.
- Emergencies: PagerDuty schedule “iDrac‑Updater‑Prod”.

---

Happy shipping! 🚀

