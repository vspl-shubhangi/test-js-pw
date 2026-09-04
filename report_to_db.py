"""
report_to_db.py
================
ETL step of the Evafi test-suite -> Apache Superset pipeline.

Apache Superset cannot read report.html directly -- it only connects to
SQL databases. This script is the bridge: it parses pytest-html's
self-contained report.html (the same #data-container[data-jsonblob] JSON
blob the browser-based dashboard.html reads) and loads it into a real
SQL database via SQLAlchemy.

WHY POSTGRES, NOT SQLITE: Superset hardcodes a security policy that
refuses to connect to SQLite databases at all ("SQLiteDialect_pysqlite
cannot be used as a data source for security reasons") -- this isn't a
misconfiguration, it's intentional upstream behavior. So this script
defaults to Postgres, which you already have local tooling for (pgAdmin).
SQLite is still supported here (e.g. for a quick local sanity-check
outside Superset) via --db-url, but Superset itself will refuse to
connect to it.

Two tables are written:

  test_runs     -- one row per pytest EXECUTION (run_id, timestamp,
                   totals, pass rate). Powers trend-over-time charts.

  test_results  -- one row per INDIVIDUAL TEST within a run (status,
                   duration, class, file, browser, device extracted from
                   the parametrize suffix, log excerpt). Powers every
                   other chart/filter/table in the Superset dashboard.

Every run APPENDS new rows tagged with a fresh run_id rather than
overwriting -- this is what lets Superset show a pass-rate trend line
across multiple executions, not just a snapshot of the latest one.

Usage:
    python report_to_db.py
    python report_to_db.py --report path/to/report.html --db-url postgresql+psycopg2://user:pass@localhost:5432/evafi_results
    EVAFI_DB_URL=postgresql+psycopg2://user:pass@localhost:5432/evafi_results python report_to_db.py

Called automatically after every pytest run via the pytest_unconfigure
hook in conftest.py -- see that file for the wiring. You can also run it
by hand any time you want to (re-)sync a report.html into the database.
"""

import argparse
import html
import json
import os
import re
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

# ─────────────────────────────────────────────────────────────────────────
# Config — set EVAFI_DB_URL in your environment (or a .env file, since
# config.py already loads one via python-dotenv) to point at your own
# Postgres instance. Falls back to a local SQLite file ONLY for people
# running this script standalone without Postgres -- remember Superset
# itself cannot connect to that SQLite fallback; it's for spot-checking
# the ETL output only (see the query examples printed at the bottom of
# this file's __main__ block).
# ─────────────────────────────────────────────────────────────────────────

DEFAULT_REPORT_PATH = os.path.join("reports", "report.html")
DEFAULT_DB_URL = os.getenv(
    "EVAFI_DB_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/evafi_results",
)
DEFAULT_SQLITE_FALLBACK_PATH = os.path.join("reports", "evafi_results.db")


def parse_duration_to_seconds(duration_str: str) -> float:
    """pytest-html uses TWO different duration formats depending on run
    length: "H:MM:SS" / "HH:MM:SS" for anything over ~a minute, and
    "N ms" / "N.NN s" for short ones. Handle both -- a real Evafi run
    (browser automation, real network calls) mostly hits the HH:MM:SS
    form, which is exactly what broke the naive "N ms"-only parser in
    the browser dashboard's duration column."""
    if not duration_str:
        return 0.0
    s = duration_str.strip()

    if re.match(r"^\d{1,2}:\d{2}:\d{2}$", s):
        h, m, sec = (int(x) for x in s.split(":"))
        return h * 3600 + m * 60 + sec

    m = re.match(r"([\d.]+)\s*(ms|s|m|h)?", s)
    if not m:
        return 0.0
    val = float(m.group(1))
    unit = m.group(2) or "ms"
    return {"ms": val / 1000, "s": val, "m": val * 60, "h": val * 3600}[unit]


# Recognized (device, browser) combo suffixes used by the matrix fixtures
# in conftest.py -- e.g. "[smartphone_android-chrome]", "[desktop-brave]",
# or a bare "[chromium]" / "[chrome]" from the single-engine fixtures.
KNOWN_DEVICES = {
    "smartphone_android", "smartphone_iphone", "tablet_android",
    "tablet_iphone", "desktop", "mobile", "tablet",
}
KNOWN_BROWSERS = {"chrome", "chromium", "firefox", "brave", "msedge", "webkit"}

# TestRegression's @pytest.mark.parametrize("case_name,payload", INVALID_CASES)
# combines with pytest-playwright's own browser parametrization to produce
# ids like "[chromium-sql_injection]" -- browser FIRST, payload-case name
# SECOND. Matches the keys of config.EVAFI_INVALID_INPUTS.
KNOWN_PAYLOAD_CASES = {
    "sql_injection", "long_string_lower", "long_string_upper",
    "long_integer", "special_characters", "unicode_text",
}


def parse_param_suffix(test_name_with_params: str):
    """Extracts device/browser/payload-case dimensions out of the pytest
    parametrize id suffix. THREE distinct bracket shapes appear across
    this suite's fixtures, and order differs between them:

        test_x[desktop-chrome]              -> device=desktop,  browser=chrome,   payload_case=None   (device FIRST)
        test_x[smartphone_iphone-msedge]     -> device=smartphone_iphone, browser=msedge, payload_case=None
        test_x[chromium-sql_injection]       -> device=None, browser=chromium, payload_case=sql_injection (browser FIRST)
        test_x[chromium]                     -> device=None, browser=chromium, payload_case=None
        test_x                               -> device=None, browser=None,     payload_case=None

    Anything that doesn't match a known shape is NOT silently discarded
    or shoved into the wrong column -- it's returned as param_raw instead,
    so it's still visible/filterable in Superset even if unrecognized.
    """
    m = re.search(r"\[([^\]]+)\]$", test_name_with_params)
    if not m:
        return None, None, None, None
    param = m.group(1)
    parts = param.split("-")

    if len(parts) >= 2 and parts[0] in KNOWN_DEVICES and parts[-1] in KNOWN_BROWSERS:
        return parts[0], parts[-1], None, None
    if len(parts) == 2 and parts[0] in KNOWN_BROWSERS and parts[1] in KNOWN_PAYLOAD_CASES:
        return None, parts[0], parts[1], None
    if param in KNOWN_BROWSERS:
        return None, param, None, None
    if param in KNOWN_DEVICES:
        return param, None, None, None
    return None, None, None, param  # unrecognized shape -> preserved raw, not misclassified


def split_test_id(test_id: str):
    """pytest testId format: 'path/to/test_file.py::ClassName::test_name[params]'"""
    parts = test_id.split("::")
    if len(parts) == 3:
        file_, cls, name = parts
    elif len(parts) == 2:
        file_, name = parts
        cls = "(module-level)"
    else:
        file_, cls, name = test_id, "(unknown)", test_id
    return os.path.basename(file_), cls, name


def extract_json_blob(html_text: str) -> dict:
    m = re.search(r'id="data-container"\s+data-jsonblob="(.*?)"(?=\s*>)', html_text, re.S)
    if not m:
        raise ValueError(
            "Could not find pytest-html's #data-container data-jsonblob in "
            "this file. Is it a pytest-html --self-contained-html report?"
        )
    return json.loads(html.unescape(m.group(1)))


# Schema statements written to work UNCHANGED on both Postgres and
# SQLite -- deliberately avoiding dialect-specific types (no SERIAL, no
# AUTOINCREMENT) so the same script serves both backends via one
# SQLAlchemy engine.
SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS test_runs (
        run_id          VARCHAR(64) PRIMARY KEY,
        run_timestamp   TIMESTAMPTZ NOT NULL,
        source_report   TEXT NOT NULL,
        total           INTEGER NOT NULL,
        passed          INTEGER NOT NULL,
        failed          INTEGER NOT NULL,
        skipped         INTEGER NOT NULL,
        errored         INTEGER NOT NULL,
        pass_rate       DOUBLE PRECISION NOT NULL,
        pytest_version  VARCHAR(32)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS test_results (
        run_id          VARCHAR(64) NOT NULL,
        test_id         TEXT NOT NULL,
        file_name       VARCHAR(255) NOT NULL,
        class_name      VARCHAR(255) NOT NULL,
        test_name       TEXT NOT NULL,
        status          VARCHAR(32) NOT NULL,
        duration_sec    DOUBLE PRECISION NOT NULL,
        device          VARCHAR(64),
        browser         VARCHAR(32),
        payload_case    VARCHAR(64),
        param_raw       TEXT,
        log_excerpt     TEXT,
        PRIMARY KEY (run_id, test_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_results_run ON test_results (run_id)",
    "CREATE INDEX IF NOT EXISTS idx_results_class ON test_results (class_name)",
    "CREATE INDEX IF NOT EXISTS idx_results_status ON test_results (status)",
    "CREATE INDEX IF NOT EXISTS idx_results_browser ON test_results (browser)",
    "CREATE INDEX IF NOT EXISTS idx_results_device ON test_results (device)",
]

# SQLite doesn't support DOUBLE PRECISION or VARCHAR(n) length limits --
# it accepts the syntax but ignores it (SQLite is dynamically typed), so
# the same statements above work as-is. The one thing that DOES differ
# is upsert syntax, handled separately in `upsert_test_results()` below.

# ── Self-updating views -- Postgres only ────────────────────────────
# These are what make the Superset dashboard require ZERO manual
# querying/filtering from anyone viewing it: point Superset's datasets
# at these views instead of the raw tables, and every chart always
# reflects the MOST RECENT test run automatically, with no date filter,
# no run_id filter, nothing for the viewer to configure.
#
# CREATE OR REPLACE VIEW is idempotent, so re-running this on every
# pytest execution (via ensure_schema(), called every time
# load_report_into_db() runs) just keeps the view definitions in sync
# with this file -- it never duplicates or breaks anything.
#
# Not created for SQLite: Superset refuses SQLite connections outright
# (see the module docstring), so there's no scenario where a Superset
# dashboard would ever query a SQLite version of these views anyway.
POSTGRES_VIEW_STATEMENTS = [
    """
    CREATE OR REPLACE VIEW latest_run_summary AS
    SELECT * FROM test_runs
    ORDER BY run_timestamp DESC
    LIMIT 1
    """,
    """
    CREATE OR REPLACE VIEW latest_run_results AS
    SELECT r.*
    FROM test_results r
    WHERE r.run_id = (SELECT run_id FROM latest_run_summary)
    """,
    """
    CREATE OR REPLACE VIEW latest_run_class_breakdown AS
    SELECT
        class_name,
        COUNT(*) FILTER (WHERE status = 'Passed')  AS passed,
        COUNT(*) FILTER (WHERE status = 'Failed')  AS failed,
        COUNT(*) FILTER (WHERE status = 'Skipped') AS skipped,
        COUNT(*) AS total,
        ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'Passed') / COUNT(*), 1) AS pass_rate_pct
    FROM latest_run_results
    GROUP BY class_name
    ORDER BY class_name
    """,
]


def ensure_schema(engine) -> None:
    with engine.begin() as conn:
        for stmt in SCHEMA_STATEMENTS:
            conn.execute(text(stmt))
        if engine.dialect.name != "sqlite":
            for stmt in POSTGRES_VIEW_STATEMENTS:
                conn.execute(text(stmt))


def upsert_test_results(engine, rows: list) -> None:
    is_sqlite = engine.dialect.name == "sqlite"
    insert_sql = (
        """
        INSERT OR REPLACE INTO test_results
        (run_id, test_id, file_name, class_name, test_name, status,
         duration_sec, device, browser, payload_case, param_raw, log_excerpt)
        VALUES (:run_id, :test_id, :file_name, :class_name, :test_name, :status,
                :duration_sec, :device, :browser, :payload_case, :param_raw, :log_excerpt)
        """
        if is_sqlite else
        """
        INSERT INTO test_results
        (run_id, test_id, file_name, class_name, test_name, status,
         duration_sec, device, browser, payload_case, param_raw, log_excerpt)
        VALUES (:run_id, :test_id, :file_name, :class_name, :test_name, :status,
                :duration_sec, :device, :browser, :payload_case, :param_raw, :log_excerpt)
        ON CONFLICT (run_id, test_id) DO UPDATE SET
            status = EXCLUDED.status,
            duration_sec = EXCLUDED.duration_sec,
            log_excerpt = EXCLUDED.log_excerpt
        """
    )
    with engine.begin() as conn:
        conn.execute(text(insert_sql), rows)


def load_report_into_db(report_path: str, db_url: str):
    if not os.path.exists(report_path):
        raise FileNotFoundError(f"report.html not found at: {report_path}")

    html_text = open(report_path, encoding="utf-8").read()
    data = extract_json_blob(html_text)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_timestamp = datetime.now(timezone.utc).isoformat()
    env = data.get("environment", {})
    pytest_version = (env.get("Packages") or {}).get("pytest", "unknown")

    rows = []
    for test_id, entries in data.get("tests", {}).items():
        entry = entries[-1] if isinstance(entries, list) else entries
        status = entry.get("result", "Unknown")
        file_name, class_name, test_name = split_test_id(test_id)
        device, browser, payload_case, param_raw = parse_param_suffix(test_name)
        duration_sec = parse_duration_to_seconds(entry.get("duration", ""))
        log_excerpt = (entry.get("log") or "")[:2000]  # cap stored log size

        rows.append({
            "run_id": run_id, "test_id": test_id, "file_name": file_name,
            "class_name": class_name, "test_name": test_name, "status": status,
            "duration_sec": duration_sec, "device": device, "browser": browser,
            "payload_case": payload_case, "param_raw": param_raw, "log_excerpt": log_excerpt,
        })

    total = len(rows)
    passed = sum(1 for r in rows if r["status"] == "Passed")
    failed = sum(1 for r in rows if r["status"] == "Failed")
    skipped = sum(1 for r in rows if r["status"] == "Skipped")
    errored = total - passed - failed - skipped
    pass_rate = round((passed / total) * 100, 2) if total else 0.0

    if db_url.startswith("sqlite"):
        # sqlite:///relative/path.db -- ensure the parent directory exists
        sqlite_path = db_url.replace("sqlite:///", "", 1)
        os.makedirs(os.path.dirname(sqlite_path) or ".", exist_ok=True)

    engine = create_engine(db_url)
    try:
        ensure_schema(engine)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """INSERT INTO test_runs
                       (run_id, run_timestamp, source_report, total, passed, failed,
                        skipped, errored, pass_rate, pytest_version)
                       VALUES (:run_id, :run_timestamp, :source_report, :total, :passed,
                               :failed, :skipped, :errored, :pass_rate, :pytest_version)"""
                ),
                {
                    "run_id": run_id, "run_timestamp": run_timestamp,
                    "source_report": os.path.abspath(report_path), "total": total,
                    "passed": passed, "failed": failed, "skipped": skipped,
                    "errored": errored, "pass_rate": pass_rate, "pytest_version": pytest_version,
                },
            )
        if rows:
            upsert_test_results(engine, rows)
    finally:
        engine.dispose()

    return run_id, total, passed, failed, skipped, errored, pass_rate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default=DEFAULT_REPORT_PATH, help="Path to pytest-html report.html")
    parser.add_argument(
        "--db-url", default=DEFAULT_DB_URL,
        help="SQLAlchemy URL, e.g. postgresql+psycopg2://user:pass@localhost:5432/evafi_results "
             "(or sqlite:///reports/evafi_results.db for a quick local check -- "
             "NOTE: Superset itself refuses SQLite connections, see module docstring)",
    )
    args = parser.parse_args()

    try:
        run_id, total, passed, failed, skipped, errored, pass_rate = load_report_into_db(
            args.report, args.db_url
        )
    except Exception as exc:
        print(f"[report_to_db] FAILED to load {args.report}: {exc}", file=sys.stderr)
        sys.exit(1)

    print(
        f"[report_to_db] Loaded run {run_id} from {args.report} into "
        f"{args.db_url.split('@')[-1] if '@' in args.db_url else args.db_url}: "
        f"{total} tests -> {passed} passed, {failed} failed, {skipped} skipped, "
        f"{errored} errored ({pass_rate}% pass rate)."
    )


if __name__ == "__main__":
    main()