"""Patient demographics, guarded by the existing authentication dependencies."""

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import UUID4
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.auth import DatabaseSession, require_roles
from app.models import Patient, Role
from app.patient_schemas import (
    PatientCreate,
    PatientPage,
    PatientResponse,
    PatientUpdate,
    SearchText,
)

router = APIRouter(prefix="/api/patients", tags=["patients"])
can_read = require_roles(Role.ADMINISTRATOR, Role.CLINIC_STAFF, Role.PHYSICIAN)
can_write = require_roles(Role.ADMINISTRATOR, Role.CLINIC_STAFF)


def find_patient(db: DatabaseSession, patient_id: UUID) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_write)],
)
def create_patient(
    payload: PatientCreate, response: Response, db: DatabaseSession
) -> Patient:
    patient = Patient(patient_id=uuid4(), **payload.model_dump())
    db.add(patient)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Patient identifier already exists"
        ) from None
    db.refresh(patient)
    response.headers["Location"] = f"/api/patients/{patient.patient_id}"
    return patient


@router.get("", response_model=PatientPage, dependencies=[Depends(can_read)])
def list_patients(
    db: DatabaseSession,
    q: Annotated[SearchText | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> PatientPage:
    filters = []
    if q is not None:
        # Escape SQL LIKE wildcards so search input is always literal text.
        full_name = Patient.first_name + " " + Patient.last_name
        name_match = full_name.icontains(q, autoescape=True)
        try:
            identifier = UUID(q)
        except ValueError:
            filters.append(name_match)
        else:
            filters.append(or_(name_match, Patient.patient_id == identifier))
    total = db.scalar(select(func.count()).select_from(Patient).where(*filters))
    patients = db.scalars(
        select(Patient)
        .where(*filters)
        .order_by(Patient.last_name, Patient.first_name, Patient.patient_id)
        .offset(offset)
        .limit(limit)
    ).all()
    return PatientPage(items=patients, total=total, limit=limit, offset=offset)


@router.get(
    "/{patient_id}", response_model=PatientResponse, dependencies=[Depends(can_read)]
)
def get_patient(patient_id: UUID4, db: DatabaseSession) -> Patient:
    return find_patient(db, patient_id)


@router.patch(
    "/{patient_id}", response_model=PatientResponse, dependencies=[Depends(can_write)]
)
def update_patient(
    patient_id: UUID4, payload: PatientUpdate, db: DatabaseSession
) -> Patient:
    patient = find_patient(db, patient_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    db.commit()
    db.refresh(patient)
    return patient
