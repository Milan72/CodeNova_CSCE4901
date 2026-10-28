# Sprint 1 — Design Baseline and Starter Implementation

This repo follows the **Sprint 1 Design Document (October 2, 2026)** and the later updated design/test plan. The original sprint produced design artifacts and seven high-fidelity prototype screens. Code here was generated as a **subsequent educational implementation**, not evidence of a tested Sprint 1 delivery.

| Screen | Implementation in this starter | Limitation |
|---|---|---|
| S01 Login and role selection | Email/password login and four server-checked roles | Demo credentials; not production authentication |
| S02 Physician overview | Role-based dashboard with appointment counts | No operational alerts or charts |
| S03 Patient directory | Staff/admin registration and searchable directory | No real patient records |
| S04 Appointment calendar | Book, confirm, check in, complete, cancel, reschedule; reject 30-minute overlaps | List view, not weekly drag-and-drop; physician availability not implemented |
| S05 Encounter workspace | Physician-only notes, saved drafts and finalize action | No clinical-grade record controls, prescriptions or interaction catalog |
| S06 Billing overview | Admin-only synthetic invoice creation/listing | No actual billing transactions or payment integration |
| S07 Patient portal | Patient-specific dashboard and appointment access | Health summaries, messages, medications and invoice views not implemented |

## Data relationships
Users (four roles); Patients (optional patient-user link); Appointments (patient, physician, creator); Encounters (one appointment, physician, SOAP note); Invoices (patient, amount in cents). These implement a subset of the proposed UML/ER models.

## Verification
Run `pytest -q` locally. Record actual results, runner, commit and environment before marking planned cases as passed. Do not enter genuine patient data. Medication interaction checking must explicitly remain unavailable rather than reporting a clear/no-interaction result.
