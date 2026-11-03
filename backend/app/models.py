"""Authentication identities and patient demographics."""

from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from email_validator import validate_email
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    String,
    Uuid,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.database import Base


class Role(str, Enum):
    ADMINISTRATOR = "administrator"
    PHYSICIAN = "physician"
    CLINIC_STAFF = "clinic_staff"
    PATIENT = "patient"


def normalize_email(value: str) -> str:
    return validate_email(value.strip(), check_deliverability=False).normalized.lower()


class User(Base):
    __tablename__ = "users"
    # JWT subjects must never be reassigned to a new account after deletion.
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254, collation="NOCASE"))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(
        SAEnum(
            Role,
            name="user_role",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda roles: [role.value for role in roles],
        )
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="ck_users_is_active"),
        server_default=true(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    @validates("email")
    def validate_email_address(self, key: str, value: str) -> str:
        return normalize_email(value)


class Patient(Base):
    __tablename__ = "patients"

    patient_id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    date_of_birth: Mapped[date] = mapped_column(Date())
    contact_email: Mapped[str | None] = mapped_column(String(254))
    phone_number: Mapped[str | None] = mapped_column(String(16))
    address: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.current_timestamp(),
        onupdate=lambda: datetime.now(timezone.utc),
    )
