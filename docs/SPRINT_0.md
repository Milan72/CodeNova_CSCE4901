# Sprint 0 — Planning & Foundation

**Project:** Clinical Management Software | **Team:** Code Nova

## Product problem
Clinics coordinate appointments, patient records, prescriptions, invoices and communications across separate workflows. The proposed app brings these tasks together in role-based workspaces.

## User roles
- Patient: view own approved information and book/cancel own appointments.
- Physician: clinical records, encounters, notes, prescribing and availability (planned modules).
- Staff: register/search patients, help with scheduling.
- Administrator: permitted clinic operations, access control, billing and reports (later implementation).

## Initial backlog
- R1 Authentication; R2 role-based access; R3 patient registration; R4 restricted clinical records; R5 booking.
- R6 rescheduling; R7 cancellation; R8 availability; R9 encounter notes; R10 prescriptions; R11 medication-interaction checking.
- R12 invoicing; R13 administrative dashboard.

## Architectural baseline
- Role-specific web UI; relational entities USER, PATIENT, APPOINTMENT, with future ENCOUNTER, PRESCRIPTION, MEDICATION and INVOICE models.
- Proposed initial application stack for this new implementation: Python / Flask / SQLite / Jinja / CSS.
- Synthetic data only. Design does not constitute HIPAA or clinical safety validation.

## Sprint 0 deliverables
Requirements baseline, use-case concepts, initial ER/UML architecture, repository structure, and test strategy. This folder implements a new code baseline based on the supplied documents; it is **not** evidence that this code existed during the original Sprint 0.

## Sprint 0 reflection and submission rubric alignment (uploaded sources)
- Aashi proposed the clinical management concept. Aashi and Sanchi prepared requirements. Karthikeya researched related clinical management software. Milan established GitHub and Trello. All four collaborated on planning.
- Initial UML/use-case design identified Patient, Physician, Clinic Staff and Administrator actors.
- The Sprint 0 rubric asks for the project/team introduction, problem and goal, functional and non-functional requirements, design diagrams and rationale, and a reflection covering accomplishments, what went well, improvements and plans for Sprint 1.
- Sprint 0 was **planning/design**, not proof of working application code. This repository contains a newly prepared implementation to help subsequent development.
