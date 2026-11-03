import pytest

from app.security import hash_password, verify_password


def test_password_hashing_uses_salted_argon2id(password):
    first = hash_password(password)
    second = hash_password(password)
    assert first.startswith("$argon2id$")
    assert first != second
    assert password not in first
    assert verify_password(password, first)
    assert not verify_password(password + "x", first)
    assert not verify_password(password, "invalid-stored-hash")


@pytest.mark.anyio
@pytest.mark.parametrize("secret", [None, "", "too-short", " " * 32])
async def test_server_rejects_missing_or_weak_secret(monkeypatch, secret):
    from app.main import app

    if secret is None:
        monkeypatch.delenv("JWT_SECRET", raising=False)
    else:
        monkeypatch.setenv("JWT_SECRET", secret)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        async with app.router.lifespan_context(app):
            pytest.fail("Server startup should reject invalid secret configuration")
