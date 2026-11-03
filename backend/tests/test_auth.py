import secrets
from datetime import datetime

import jwt
import pytest

from app.models import Role, User
from app.security import JWT_ALGORITHM, JWT_AUDIENCE, JWT_ISSUER

pytestmark = pytest.mark.anyio


async def login_as(client, account, password):
    response = await client.post(
        "/api/auth/login", json={"email": account.email, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.mark.parametrize("role", list(Role))
async def test_successful_login(client, accounts, password, jwt_secret, role):
    user = accounts[role.value]
    response = await client.post(
        "/api/auth/login", json={"email": user.email, "password": password}
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "token_type", "expires_in"}
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    claims = jwt.decode(
        body["access_token"], jwt_secret, algorithms=[JWT_ALGORITHM],
        audience=JWT_AUDIENCE, issuer=JWT_ISSUER,
    )
    assert claims["sub"] == str(user.id)
    assert claims["exp"] - claims["iat"] == 900
    assert set(claims) == {"sub", "iat", "exp", "iss", "aud"}
    assert response.headers["cache-control"] == "no-store"
    assert password not in response.text
    assert user.password_hash.startswith("$argon2id$")
    assert user.password_hash not in response.text


@pytest.mark.parametrize(
    ("account_name", "correct_password"),
    [("patient", False), ("nonexistent", True), ("inactive", True), ("inactive", False)],
)
async def test_invalid_credentials_are_indistinguishable(
    client, accounts, password, account_name, correct_password
):
    email = (
        accounts[account_name].email if account_name in accounts
        else "nonexistent@example.com"
    )
    response = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password if correct_password else password + "x"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect email or password"}
    assert response.headers["www-authenticate"] == "Bearer"
    assert "access_token" not in response.json()


async def test_login_normalizes_email(client, accounts, password):
    response = await client.post(
        "/api/auth/login",
        json={"email": "  PATIENT@EXAMPLE.COM  ", "password": password},
    )
    assert response.status_code == 200


@pytest.mark.parametrize("path", ["/api/auth/me", "/api/admin/check"])
@pytest.mark.parametrize("authorization", [None, "Basic invalid", "Bearer"])
async def test_missing_bearer_token(client, path, authorization):
    headers = {} if authorization is None else {"Authorization": authorization}
    response = await client.get(path, headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "case",
    [
        "malformed", "wrong_signature", "wrong_algorithm", "unsigned", "expired",
        "missing_exp", "missing_iat", "missing_sub", "wrong_issuer", "wrong_audience",
        "future_iat", "invalid_sub", "oversized_sub", "negative_sub", "numeric_sub",
        "invalid_exp_type", "infinite_exp",
    ],
)
async def test_invalid_and_expired_tokens(client, accounts, signed_token, case):
    user_id = accounts["patient"].id
    options = {
        "wrong_signature": {"key": secrets.token_urlsafe(48)},
        "wrong_algorithm": {"algorithm": "HS384"},
        "unsigned": {"algorithm": "none", "key": ""},
        "expired": {"claims": {"exp": 0}},
        "missing_exp": {"omit": ["exp"]},
        "missing_iat": {"omit": ["iat"]},
        "missing_sub": {"omit": ["sub"]},
        "wrong_issuer": {"claims": {"iss": "another-service"}},
        "wrong_audience": {"claims": {"aud": "another-service"}},
        "future_iat": {"claims": {"iat": 4102444800}},
        "invalid_sub": {"claims": {"sub": "not-an-id"}},
        "oversized_sub": {"claims": {"sub": str(2**63)}},
        "negative_sub": {"claims": {"sub": "-1"}},
        "numeric_sub": {"claims": {"sub": user_id}},
        "invalid_exp_type": {"claims": {"exp": []}},
        "infinite_exp": {"claims": {"exp": float("inf")}},
    }
    token = "not-a-jwt" if case == "malformed" else signed_token(user_id, **options[case])
    response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}
    assert response.headers["www-authenticate"] == "Bearer"


async def test_me_returns_only_public_profile(client, accounts, password):
    user = accounts["patient"]
    token = await login_as(client, user, password)
    response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    profile = response.json()
    assert set(profile) == {"id", "email", "role", "is_active", "created_at", "updated_at"}
    assert profile["id"] == user.id
    assert profile["email"] == user.email
    assert profile["role"] == "patient"
    assert profile["is_active"] is True
    for field in ("created_at", "updated_at"):
        assert datetime.fromisoformat(profile[field].replace("Z", "+00:00")).tzinfo is not None
    assert user.password_hash not in response.text
    assert password not in response.text
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("role", "expected_status"),
    [("administrator", 200), ("physician", 403), ("clinic_staff", 403), ("patient", 403)],
)
async def test_administrator_access_and_role_restrictions(
    client, accounts, password, role, expected_status
):
    token = await login_as(client, accounts[role], password)
    response = await client.get(
        "/api/admin/check", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == expected_status
    assert response.json() == (
        {"status": "ok"} if expected_status == 200 else {"detail": "Insufficient permissions"}
    )


@pytest.mark.parametrize("change", ["deactivate", "delete"])
async def test_account_state_is_rechecked(
    client, accounts, password, migrated_database, change
):
    account = accounts["administrator"]
    token = await login_as(client, account, password)
    with migrated_database.SessionLocal() as session:
        user = session.get(User, account.id)
        if change == "deactivate":
            user.is_active = False
        else:
            session.delete(user)
        session.commit()
    response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_role_change_applies_to_existing_token(
    client, accounts, password, migrated_database
):
    account = accounts["administrator"]
    token = await login_as(client, account, password)
    with migrated_database.SessionLocal() as session:
        user = session.get(User, account.id)
        user.role = Role.PATIENT
        session.commit()
    response = await client.get(
        "/api/admin/check", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


async def test_role_claim_cannot_override_database_role(client, accounts, signed_token):
    token = signed_token(accounts["patient"].id, claims={"role": "administrator"})
    response = await client.get(
        "/api/admin/check", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


async def test_unknown_user_token(client, signed_token):
    token = signed_token(2**62)
    response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_deleted_identity_cannot_be_reused(
    client, account_factory, password, migrated_database
):
    original = account_factory("original@example.com")
    token = await login_as(client, original, password)
    with migrated_database.SessionLocal() as session:
        session.delete(session.get(User, original.id))
        session.commit()
    replacement = account_factory("replacement@example.com", Role.ADMINISTRATOR)
    assert replacement.id != original.id
    response = await client.get(
        "/api/admin/check", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


@pytest.mark.parametrize("case", ["password_object", "long_password", "invalid_email", "role"])
async def test_validation_does_not_echo_credentials(client, password, case):
    body = {"email": "patient@example.com", "password": password}
    if case == "password_object":
        body["password"] = {"private": password}
    elif case == "long_password":
        body["password"] = password * 100
    elif case == "invalid_email":
        body["email"] = "invalid-email"
    else:
        body["role"] = "administrator"
    response = await client.post("/api/auth/login", json=body)
    assert response.status_code == 422
    assert password not in response.text
    assert all("input" not in error for error in response.json()["detail"])


async def test_missing_secret_fails_closed_after_startup(client, monkeypatch, password):
    monkeypatch.delenv("JWT_SECRET")
    response = await client.post(
        "/api/auth/login", json={"email": "patient@example.com", "password": password}
    )
    assert response.status_code == 503
    assert "access_token" not in response.json()
    response = await client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 503


async def test_no_public_registration(client):
    response = await client.post("/api/auth/register", json={})
    assert response.status_code == 404
