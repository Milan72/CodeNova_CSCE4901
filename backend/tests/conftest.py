"""Temporary databases and synthetic identities; no development database access."""

import secrets
from datetime import datetime, timezone
from pathlib import Path

import jwt
import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    from app import database as database_module

    test_engine = database_module.create_db_engine()
    monkeypatch.setattr(database_module, "engine", test_engine)
    monkeypatch.setattr(database_module, "SessionLocal", sessionmaker(bind=test_engine))
    try:
        yield database_module
    finally:
        test_engine.dispose()


@pytest.fixture
def migrated_database(database):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    return database


@pytest.fixture
def jwt_secret(monkeypatch):
    secret = secrets.token_urlsafe(48)
    monkeypatch.setenv("JWT_SECRET", secret)
    return secret


@pytest.fixture
def password():
    return secrets.token_urlsafe(24)


@pytest.fixture
def account_factory(migrated_database, password):
    from app.models import Role, User
    from app.security import hash_password

    def create_account(email, role=Role.PATIENT, *, is_active=True):
        user = User(
            email=email,
            password_hash=hash_password(password),
            role=role,
            is_active=is_active,
        )
        with migrated_database.SessionLocal() as session:
            session.add(user)
            session.commit()
            session.refresh(user)
        return user

    return create_account


@pytest.fixture
def accounts(account_factory):
    from app.models import Role

    users = {
        role.value: account_factory(f"{role.value}@example.com", role)
        for role in Role
    }
    users["inactive"] = account_factory("inactive@example.com", is_active=False)
    return users


@pytest.fixture
async def client(migrated_database, jwt_secret):
    from app.main import app

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http_client:
            yield http_client


@pytest.fixture
def signed_token(jwt_secret):
    from app.security import ACCESS_TOKEN_SECONDS, JWT_ALGORITHM, JWT_AUDIENCE, JWT_ISSUER

    def make_token(user_id, *, claims=None, omit=(), key=None, algorithm=JWT_ALGORITHM):
        now = int(datetime.now(timezone.utc).timestamp())
        payload = {
            "sub": str(user_id), "iat": now, "exp": now + ACCESS_TOKEN_SECONDS,
            "iss": JWT_ISSUER, "aud": JWT_AUDIENCE,
        }
        payload.update(claims or {})
        for claim in omit:
            payload.pop(claim)
        return jwt.encode(
            payload, jwt_secret if key is None else key, algorithm=algorithm
        )

    return make_token


@pytest.fixture
def patient_payload():
    return {
        "first_name": "Casey",
        "last_name": "Example",
        "date_of_birth": "1990-01-02",
        "contact_email": "casey.patient@example.com",
        "phone_number": "+19405550101",
        "address": "100 Synthetic Lane, Example City, TX 00000",
    }


@pytest.fixture
def patient_factory(migrated_database, patient_payload):
    from app.models import Patient
    from app.patient_schemas import PatientCreate

    def create_patient(**changes):
        data = PatientCreate(**(patient_payload | changes)).model_dump()
        patient = Patient(**data)
        with migrated_database.SessionLocal() as session:
            session.add(patient)
            session.commit()
            session.refresh(patient)
        return patient

    return create_patient


@pytest.fixture
def headers_for(account_factory, signed_token):
    from app.models import Role

    headers = {}

    def make_headers(role="administrator"):
        role = Role(role)
        if role not in headers:
            user = account_factory(f"{role.value}@example.com", role)
            headers[role] = {"Authorization": f"Bearer {signed_token(user.id)}"}
        return headers[role]

    return make_headers
