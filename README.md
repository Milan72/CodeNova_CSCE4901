# Code Nova — Clinical Management Software

A **runnable educational starter implementation** based on Code Nova's Sprint 0 planning and Sprint 1 design. The original Sprint 1 deliverables described a high-fidelity prototype; this repository is a new implementation, not proof that all original requirements were built or tested at that time.

## Start locally (macOS / Windows / Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
flask --app app init-db
flask --app app run --debug
```

Open **http://127.0.0.1:5000**.

## Demo credentials — synthetic data only

All passwords: `DemoPass123!`

| Role | Email |
|---|---|
| Admin | admin.demo@example.test |
| Physician | doctor.demo@example.test |
| Staff | staff.demo@example.test |
| Patient | patient.demo@example.test |

Database is stored in `code_nova.db` and ignored by Git.

## Tests

```bash
pytest -q
```

## Sprint documentation
- [Sprint 0](docs/SPRINT_0.md)
- [Sprint 1](docs/SPRINT_1.md)

## Project structure
- `app.py` — Python Flask routes, authentication, SQLite schema and demo seed.
- `templates/` — role-specific HTML pages.
- `static/style.css` — responsive user interface.
- `tests/` — authorization, CSRF, CRUD and booking conflict tests.

## Safety / limits
**Not for production or real patient information.** Demo passwords are public. Default development secret must be replaced, and deployment would require HTTPS, validated data handling, stronger session protection, production secrets, auditing, authorization reviews, clinical validation, and more. No drug interaction checks, real payment processing, HIPAA compliance, or notification dispatch is implemented. Invoice entries are synthetic only. Physician SOAP notes are demo-only. Booking assumes fixed 30-minute slots and does not yet support physician availability. Do not use it for patient care.

## GitHub commands

```bash
git init
git add .
git commit -m "Add Code Nova Sprint 0 docs and Sprint 1 app starter"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

If your team already has a repo, copy into a new feature branch and open a pull request instead of overwriting existing work.


## Sprint 1 screens from the supplied design
S01 Login (`/login`), S02 dashboard (`/dashboard`), S03 patient directory (`/patients`), S04 appointments (`/appointments`), S05 physician notes (`/encounters`), S06 admin billing (`/billing`), and S07 patient portal (`/dashboard` when signed in as patient). All seven are represented, but several original prototype capabilities remain unimplemented.

## Additional source documents
Sprint 0 reflection, Sprint 0 presentation rubric, original Sprint 1 Design Document, updated Sprint 1 design, test plan, product requirements, Sprint 1 reflection, and change log.
