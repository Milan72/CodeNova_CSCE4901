# Clinical Management System

## CSCE 4901 Capstone Project

A clinical management system designed to streamline clinic
operations including patient management, scheduling,
clinical documentation, prescriptions, billing, communication,
and administrative functions.

The system also includes a medication safety module designed
to identify potential drug-drug interactions and alert physicians
before a prescription is finalized.

## Team

- Sanchi Shah
- Aashi Patel
- Karthikeya Pullemala
- Milan Chaulagain

## Technologies

To be determined during requirements analysis.

## Project Status

Sprint 0 - Requirements Gathering

## Project Goals

- Improve clinic management
- Simplify appointment scheduling
- Improve patient communication

## Code Nova Backend — Milestone 1

The sections above preserve the initial project planning information. Milestone 1
introduced a minimal FastAPI backend with one health endpoint. Milestone 2 adds
database infrastructure, documented below. Other application features remain planned.

### Local setup (macOS)

Prerequisite: Python 3.10 or newer with `venv` and `pip` available. From the
repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Dependencies are pinned in `backend/requirements.txt` and installed only in the
local virtual environment. The health endpoint needs no database configuration.

### Start the development server

From `backend/`, with the virtual environment activated:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, check the endpoint:

```bash
curl -i http://127.0.0.1:8000/api/health
```

Expected: HTTP `200 OK` with the JSON body `{"status":"ok"}`.
Interactive API documentation is available at <http://127.0.0.1:8000/docs>.
Application endpoints use the `/api` prefix for future frontend integration.
Stop the server with `Ctrl+C`.

### Run the tests

From `backend/`, with the virtual environment activated:

```bash
python -m pytest -q
```

The test uses HTTPX to call the app in memory and checks the HTTP status and exact
response JSON; a running server is not required. The async test uses AnyIO's
Pytest plugin, included through the FastAPI/HTTPX dependencies, with the `asyncio`
backend.

In a new terminal, run `cd backend` from the repository root and
`source .venv/bin/activate` before starting the server or tests. Run `deactivate`
when finished. Virtual environments, secrets, local SQLite files, and generated
caches are excluded from Git by `.gitignore`.

## Database Infrastructure — Milestone 2

SQLAlchemy 2.x provides the engine, declarative `Base`, and session factory in
`backend/app/database.py`. Future FastAPI routes can use `Depends(get_db)` for a
session that closes after each request, including errors. Transactions must be
committed explicitly; the dependency does not automatically commit changes.

### Database configuration

From `backend/`, activate `.venv` and install the updated dependencies:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Without `DATABASE_URL`, both the app and Alembic use `backend/code_nova.db`,
resolved to an absolute path. The database is created on the first connection.
To use a different local SQLite file, set the variable before starting the server
or running migrations:

```bash
export DATABASE_URL="sqlite:///./code_nova.local.db"
```

Relative SQLite URLs use the current working directory. For an absolute path,
use `sqlite:////absolute/path/to/code_nova.db`; the parent directory must exist.
Run `unset DATABASE_URL` to restore the default and restart any running server
after changing it. `.env` files are not loaded automatically. Local database
files and `.env` files are ignored by Git; keep credentials out of tracked files.

### Run migrations

From `backend/`, with the same environment configuration as the server:

```bash
python -m alembic upgrade head
python -m alembic current
```

The initial empty baseline is revision `0001`; `current` should show `0001 (head)`.
It creates only Alembic's `alembic_version` tracking table. Domain tables are not
defined yet. Alembic uses the same engine configuration and `Base.metadata` as
the app; schema changes are managed through migration files, not `create_all()`.

Run `python -m pytest -q` for all tests. Database tests use temporary SQLite files
and cover `SELECT 1`, session cleanup, and baseline migration upgrade/downgrade.
They do not connect to the development database. `/api/health` remains an
application health check and does not check database connectivity.
