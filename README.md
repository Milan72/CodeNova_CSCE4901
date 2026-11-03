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

The sections above preserve the initial project planning information. The current
implementation is a minimal FastAPI backend with one health endpoint. Other
application features remain planned.

### Local setup (macOS)

Prerequisite: Python 3.10 or newer with `venv` and `pip` available. From the
repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The four direct dependencies (FastAPI, Uvicorn, Pytest, and HTTPX) are pinned in
`backend/requirements.txt`. Packages are installed only in the local virtual
environment. No environment variables or database are needed for this milestone.

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
