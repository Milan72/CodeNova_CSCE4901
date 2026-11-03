"""Password hashing and strictly validated, short-lived access tokens."""

import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "code-nova"
JWT_AUDIENCE = "code-nova-api"
ACCESS_TOKEN_SECONDS = 15 * 60

_password_hasher = PasswordHasher(type=Type.ID)


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# Unknown accounts still perform an Argon2 verification to reduce timing differences.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


def read_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret or not secret.strip() or len(secret.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 bytes of random secret data.")
    return secret


def create_access_token(user_id: int, secret: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(seconds=ACCESS_TOKEN_SECONDS),
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
        },
        secret,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str, secret: str) -> int:
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["sub", "iat", "exp", "iss", "aud"]},
        )
        subject = claims["sub"]
        if (
            not isinstance(subject, str)
            or not subject.isascii()
            or not subject.isdecimal()
            or len(subject) > 19
        ):
            raise jwt.InvalidTokenError("Invalid subject")
        user_id = int(subject)
        if not 0 < user_id <= 2**63 - 1:
            raise jwt.InvalidTokenError("Invalid subject")
        return user_id
    except (ValueError, TypeError, OverflowError) as exc:
        raise jwt.InvalidTokenError("Invalid token claims") from exc
