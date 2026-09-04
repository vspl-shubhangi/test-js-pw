# EvaFi Test Execution Dashboard

Automated Playwright/pytest test suite for EvaFi, with results automatically loaded into PostgreSQL and visualized in an Apache Superset dashboard.

## What this project does

1. `pytest` runs the test suite (parallel execution across multiple browsers/devices).
2. A `pytest` hook in `report_to_db.py` automatically loads results from `report.html` into a PostgreSQL database after every run.
3. Apache Superset (running in Docker) connects to that database and visualizes pass/fail trends, slowest tests, browser-specific failures, and more — no manual chart rebuilding needed between runs.

---

## Project structure

```
.
├── config.py                  # Test configuration
├── conftest.py                # pytest fixtures
├── docker-compose.superset.yml  # Postgres + Superset containers
├── Dockerfile                 # Extends apache/superset:latest with the psycopg2 driver
├── pytest.ini                 # pytest configuration
├── reports/                   # Generated test reports (gitignored)
├── report_to_db.py            # Loads report.html results into Postgres after each run
├── requirements.txt           # Python dependencies
├── tests/                     # Test suite (one file per test class/area)
└── wizard_helpers.py          # Shared test helper functions
```

---

## Prerequisites

- **Docker Engine**, installed via the **official apt repository** — not the `snap install docker` package. The snap version has a known AppArmor bug that blocks stopping/restarting containers. If you already have snap Docker installed:
  ```bash
  sudo snap remove docker
  ```
  Then install via apt: https://docs.docker.com/engine/install/ubuntu/
- **Python 3.10+** and `venv`
- Ports **5432** (Postgres) and **8088** (Superset) free on your host. If you have a separate host-installed Postgres, stop it first:
  ```bash
  sudo systemctl stop postgresql
  sudo systemctl disable postgresql
  ```

---

## First-time setup

### 1. Clone and enter the project
```bash
git clone <your-new-repo-url>
cd <your-project-folder>
```

### 2. Set up the Python environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Start Postgres + Superset
```bash
docker compose -f docker-compose.superset.yml up -d --build
docker ps   # confirm both containers show "healthy"
```

### 4. Initialize Superset (first run only)
```bash
docker compose -f docker-compose.superset.yml exec superset superset fab create-admin \
    --username admin --firstname Admin --lastname User --email admin@example.com --password admin
docker compose -f docker-compose.superset.yml exec superset superset db upgrade
docker compose -f docker-compose.superset.yml exec superset superset init
```

### 5. Confirm the Postgres driver is installed correctly
```bash
docker exec -it evafi_superset /app/.venv/bin/python3 -c "import psycopg2; print('OK')"
```
Should print `OK`. If it doesn't, see Troubleshooting below — this is the single most common setup snag.

### 6. Run the test suite
```bash
source venv/bin/activate
pytest
```
Watch for this line at the end:
```
[Superset pipeline] Loaded run <run_id> into localhost:5432/evafi_results: ...
```
That confirms results were written to Postgres successfully.

### 7. Open Superset and connect the database
Go to `http://localhost:8088`, log in as `admin` / `admin`.

Data → Databases → + Database → PostgreSQL:

| Field | Value |
|---|---|
| Host | `postgres` |
| Port | `5432` |
| Database name | `evafi_results` |
| Username | `postgres` |
| Password | `postgres` |
| Display Name | `EvaFi Results` |

### 8. Register datasets
`report_to_db.py` automatically creates several tables/views. Register each as a Superset dataset (Data → Datasets → + Dataset → schema `public`):

| Dataset | Scope | Use for |
|---|---|---|
| `test_runs` | All runs, historical | Trend charts over time |
| `test_results` | All runs, historical, per-test | Historical per-test analysis |
| `latest_run_summary` | Most recent run, 1 row | Headline "current status" numbers |
| `latest_run_results` | Most recent run, per-test | Per-test breakdowns of the current run |
| `latest_run_class_breakdown` | Most recent run, per-class | Pre-aggregated pass/fail/skip counts by test class |

### 9. Build the dashboard
Charts → + Chart, using the datasets above. See the project's dashboard-building notes (or ask for the full chart-by-chart guide) for exact configurations — the short version:

- **Big Number**: `latest_run_summary`, metric `pass_rate`
- **Pie**: `latest_run_results`, dimension `status`, metric `COUNT(*)`
- **Line (trend)**: `test_runs`, x-axis `run_timestamp`, metric `pass_rate`
- **Bar (top failures)**: `latest_run_results`, x-axis `test_name`, metric `COUNT(*)`, filter `status = Failed`
- **Bar (by class)**: `latest_run_class_breakdown`, x-axis `class_name`, metric `SUM(failed)`
- **Box Plot (durations)**: `latest_run_results`, group by `class_name`, metric `duration_sec`
- **Bar (by browser)**: `latest_run_results`, x-axis `browser`, metric `COUNT(*)`, filter `status = Failed`
- **Table (detail)**: `latest_run_results`, raw record columns

Save each chart to the same dashboard (e.g. "EvaFi Test Execution Dashboard").

---

## Daily workflow

```bash
# 1. Start containers
cd <project-folder>
docker compose -f docker-compose.superset.yml up -d

# 2. Confirm both are healthy
docker ps

# 3. Run tests (venv, same directory)
source venv/bin/activate
pytest

# 4. Open the dashboard
# http://localhost:8088 → Dashboards → EvaFi Test Execution Dashboard
# Click the refresh icon — new results appear automatically, no chart rebuilding needed
```

**Important:** Docker containers must be running *before* pytest finishes, or `report_to_db.py` will fail with `Connection refused` and results won't be saved.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'psycopg2'` inside the Superset container**
The Superset image runs its own Python venv at `/app/.venv`, separate from the system Python. The Dockerfile must install into that specific venv:
```dockerfile
FROM apache/superset:latest
USER root
RUN /app/.venv/bin/python3 -m ensurepip --upgrade && /app/.venv/bin/python3 -m pip install psycopg2-binary
USER superset
```
After editing, force a real rebuild (an image rebuild alone doesn't always recreate a running container of the same name):
```bash
docker compose -f docker-compose.superset.yml build --no-cache superset
docker compose -f docker-compose.superset.yml rm -sf superset
docker compose -f docker-compose.superset.yml up -d
```

**`Connection refused` when pytest tries to write to Postgres**
Docker containers weren't running when the test suite finished. Always run `docker compose up -d` and confirm `docker ps` shows both containers healthy *before* running `pytest`.

**`password authentication failed for user "postgres"`**
Postgres only applies `POSTGRES_PASSWORD` when initializing a genuinely empty data volume. If you're reusing an old `evafi_pg_data` volume from before a password/config change, it keeps the old password. Fix with a full reset (this deletes current data — repopulate by re-running pytest afterward):
```bash
docker compose -f docker-compose.superset.yml down -v
docker compose -f docker-compose.superset.yml up -d --build
```

**`docker stop` / `docker restart` fails with `permission denied`, even with `sudo`**
This is a known AppArmor bug specific to **snap-installed Docker** on Ubuntu (`snap install docker`). Check with:
```bash
snap list docker
sudo dmesg | grep -i apparmor | grep -i denied
```
Fix: uninstall the snap package and install Docker via the official apt repository instead (see Prerequisites above).

**Superset UI shows "Internal server error"**
Usually means `superset_home` (Superset's own metadata volume) is empty/fresh and the one-time setup commands haven't been run yet. Re-run the `fab create-admin` / `db upgrade` / `superset init` sequence from step 4.

**Dockerfile changes seem to have no effect**
Docker looks for a file named exactly `Dockerfile` (capital D) by default. Confirm with `ls -la` — a lowercase `dockerfile` won't be picked up by `build: .` in the compose file on a case-sensitive filesystem.

---

## .gitignore recommendations

```
venv/
__pycache__/
*.pyc
reports/
.pytest_cache/
Dockerfile.bak
```

Don't commit `reports/evafi_results.db`, `reports/report.html`, or `reports/screenshots/` — these are generated per test run, not source code. If you want a Postgres data snapshot in version control instead, use `pg_dump` and commit a `.sql` file separately, not the raw report artifacts.