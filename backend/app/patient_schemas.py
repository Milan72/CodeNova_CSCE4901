"""Validated demographic inputs and explicit patient response contracts."""

import re
from datetime import date, datetime, timezone
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    UUID4,
    field_validator,
    model_validator,
)

from app.models import normalize_email


def printable_text(value: str) -> str:
    if not value.isprintable():
        raise ValueError("Control characters are not allowed")
    return value


def person_name(value: str) -> str:
    printable_text(value)
    if not any(character.isalpha() for character in value):
        raise ValueError("A name must contain a letter")
    return value


def birth_date(value: object) -> date:
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            raise ValueError("Use a valid calendar date in YYYY-MM-DD format") from None
    if type(value) is not date:
        raise ValueError("Use a date in YYYY-MM-DD format")
    if value > datetime.now(timezone.utc).date():
        raise ValueError("Date of birth cannot be in the future")
    return value


Name = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    AfterValidator(person_name),
]
BirthDate = Annotated[date, BeforeValidator(birth_date)]
ContactEmail = Annotated[
    EmailStr, Field(max_length=254), AfterValidator(normalize_email)
]
PhoneNumber = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^\+[1-9][0-9]{7,14}$"),
]
Address = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    AfterValidator(printable_text),
]
SearchText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=201),
    AfterValidator(printable_text),
]


class PatientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: Name
    last_name: Name
    date_of_birth: BirthDate
    contact_email: ContactEmail | None = None
    phone_number: PhoneNumber | None = None
    address: Address | None = None


class PatientUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: Name | None = None
    last_name: Name | None = None
    date_of_birth: BirthDate | None = None
    contact_email: ContactEmail | None = None
    phone_number: PhoneNumber | None = None
    address: Address | None = None

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("Supply at least one field to update")
        for field in ("first_name", "last_name", "date_of_birth"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError("Names and date of birth cannot be null")
        return self


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: UUID4
    first_name: str
    last_name: str
    date_of_birth: date
    contact_email: str | None
    phone_number: str | None
    address: str | None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def timestamps_as_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class PatientPage(BaseModel):
    items: list[PatientResponse]
    total: int
    limit: int
    offset: int
