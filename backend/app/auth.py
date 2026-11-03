"""Authentication routes and reusable authorization dependencies."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Role, User
from app.schemas import LoginRequest, TokenResponse, UserPublic
from app.security import (
    ACCESS_TOKEN_SECONDS,
    DUMMY_PASSWORD_HASH,
    create_access_token,
    decode_access_token,
    read_jwt_secret,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
admin_router = APIRouter(prefix="/api/admin", tags=["administration"])
bearer = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[Session, Depends(get_db)]


def unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
    )


def get_signing_secret() -> str:
    try:
        return read_jwt_secret()
    except RuntimeError as exc:
        # Also fail closed if configuration is lost after successful startup.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        ) from exc


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: DatabaseSession,
    secret: Annotated[str, Depends(get_signing_secret)],
) -> User:
    if credentials is None:
        raise unauthorized()
    try:
        user_id = decode_access_token(credentials.credentials, secret)
    except InvalidTokenError as exc:
        raise unauthorized() from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized()
    return user


def require_roles(*allowed_roles: Role) -> Callable[..., User]:
    def check_role(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return user

    return check_role


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    response: Response,
    db: DatabaseSession,
    secret: Annotated[str, Depends(get_signing_secret)],
) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == credentials.email))
    password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
    password_valid = verify_password(credentials.password.get_secret_value(), password_hash)
    if user is None or not password_valid or not user.is_active:
        raise unauthorized("Incorrect email or password")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return TokenResponse(
        access_token=create_access_token(user.id, secret),
        expires_in=ACCESS_TOKEN_SECONDS,
    )


@router.get("/me", response_model=UserPublic)
def me(response: Response, user: Annotated[User, Depends(get_current_user)]) -> User:
    response.headers["Cache-Control"] = "no-store"
    return user


@admin_router.get("/check", dependencies=[Depends(require_roles(Role.ADMINISTRATOR))])
def administrator_check() -> dict[str, str]:
    return {"status": "ok"}
