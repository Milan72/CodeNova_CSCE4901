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
introduced a minimal FastAPI backend with one health endpoint. Milestone 2 added
database infrastructure; Milestone 3 adds authentication and role-based access.
Other application features remain planned.

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

From `backend/`, with the virtual environment activated, generate a local signing
secret, apply migrations, and start the server:

```bash
export JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Generate the secret once per development shell and keep it private. Use the same
secret across restarts/workers to keep existing tokens valid. Generating a new
value invalidates previously issued tokens. See Milestone 3 below for configuration.

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

Tests use HTTPX to call the app in memory; a running server is not required.
Async tests use AnyIO's Pytest plugin, included through the FastAPI/HTTPX
dependencies, with the `asyncio` backend. Authentication tests generate their own
temporary signing secrets and synthetic accounts.

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

The initial empty baseline is revision `0001`. Milestone 3 adds revision `0002`
for the `users` table; `current` should now show `0002 (head)`. Neither migration
seeds accounts. Alembic uses the same engine configuration and `Base.metadata` as
the app; schema changes are managed through migration files, not `create_all()`.

Run `python -m pytest -q` for all tests. Database tests use temporary SQLite files
and cover `SELECT 1`, session cleanup, and baseline migration upgrade/downgrade.
They do not connect to the development database. `/api/health` remains an
application health check and does not check database connectivity.

## Authentication and RBAC — Milestone 3

### Environment variables

| Variable | Requirement |
| --- | --- |
| `JWT_SECRET` | Required for server startup; at least 32 bytes of cryptographically random secret data. No default. |
| `DATABASE_URL` | Optional; defaults to the SQLite file at `backend/code_nova.db`. |

Set variables in the server's environment; `.env` files are not loaded
automatically. Never add secrets to Git. Missing, blank, or too-short signing
secrets stop server startup. If signing configuration becomes unavailable after
startup, authentication requests fail closed with HTTP 503.

For an existing checkout, activate `backend/.venv` and run
`python -m pip install -r requirements.txt` before the startup commands above.
Migrations do not require a JWT secret. Accounts are created only by test fixtures
in this milestone; the development database starts without accounts. There is no
public registration or default administrator credential.

### Endpoints

| Endpoint | Request / permission | Success |
| --- | --- | --- |
| `POST /api/auth/login` | JSON containing `email` and `password` | `access_token`, `token_type: "bearer"`, `expires_in: 900` |
| `GET /api/auth/me` | `Authorization: Bearer <access_token>` | Public profile: `id`, `email`, `role`, `is_active`, `created_at`, `updated_at` |
| `GET /api/admin/check` | Bearer token for an active administrator | `{"status":"ok"}` |
| `GET /api/health` | No authentication | `{"status":"ok"}` |

Login accepts JSON, not OAuth2 form data. Email addresses are normalized and
matched without case sensitivity. Incorrect passwords, unknown accounts, and
inactive accounts receive the same HTTP 401 response: `Incorrect email or password`.
Invalid request bodies receive HTTP 422 without echoing credentials.

Protected endpoints return HTTP 401 with `WWW-Authenticate: Bearer` for missing,
invalid, expired, or unusable tokens. Authenticated users without the required
role receive HTTP 403. Public profiles never include password hashes. In `/docs`,
use the bearer **Authorize** control with a token returned by login.

Exactly four roles are supported: `administrator`, `physician`, `clinic_staff`,
and `patient`. Reusable dependencies in `app/auth.py` are `get_current_user` and
`require_roles`, for example `Depends(require_roles(Role.ADMINISTRATOR))`.
The current database role and active status are checked on each request, so
deactivation, deletion, and role changes apply to already-issued tokens.

### Verification and security notes

From `backend/`, with `.venv` activated:

```bash
python -m pytest -q
python -m pip check
```

Tests use temporary SQLite databases migrated from scratch, random test secrets,
and synthetic accounts defined in fixtures. They cover all four roles, login
failures, token validation/expiry, public profile filtering, session cleanup,
schema constraints, and migration upgrade/downgrade. The development database is
never used by tests.

- Passwords are stored as salted Argon2id hashes. Unknown-account login attempts
  also perform Argon2 verification to reduce timing differences.
- Access tokens expire after 15 minutes. Validation fixes the algorithm to HS256
  and checks signature, expiry, issued-at time, issuer, audience, and user ID.
  Tokens contain no passwords, hashes, email addresses, or authoritative roles.
  SQLite user IDs are not reused after deletion, so old tokens cannot identify
  replacement accounts.
- Login/profile responses prohibit caching. Request validation omits submitted
  values so malformed requests do not reflect passwords in error responses.
- Timestamps are UTC; `updated_at` is maintained on SQLAlchemy ORM updates.
- Keep tokens and signing secrets out of logs, URLs, and source control. Use HTTPS
  and deployment-level login rate limiting before exposing the server publicly.
- Refresh tokens, individual token revocation/logout, password reset, account
  provisioning, and application-level rate limiting are not implemented yet.
  Deactivating an account blocks its tokens; changing the signing secret invalidates
  all tokens. No clinical CRUD or frontend changes are part of this milestone.
