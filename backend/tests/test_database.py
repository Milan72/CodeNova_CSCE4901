from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError


def test_database_connection_and_session_cleanup(database):
    with contextmanager(database.get_db)() as session:
        assert session.execute(text("SELECT 1")).scalar_one() == 1

    assert database.engine.pool.checkedout() == 0


def test_session_cleanup_after_error(database):
    with pytest.raises(RuntimeError, match="synthetic failure"):
        with contextmanager(database.get_db)() as session:
            session.execute(text("SELECT 1"))
            raise RuntimeError("synthetic failure")

    assert database.engine.pool.checkedout() == 0


def test_empty_baseline_migration(database):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "0001")

    assert inspect(database.engine).get_table_names() == ["alembic_version"]
    with database.engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        assert revision == "0001"

    command.downgrade(config, "base")
    with database.engine.connect() as connection:
        assert connection.execute(
            text("SELECT COUNT(*) FROM alembic_version")
        ).scalar_one() == 0


def test_fresh_database_migrations(database):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    assert inspect(database.engine).get_table_names() == ["alembic_version", "users"]
    with database.engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
        assert connection.scalar(text("SELECT COUNT(*) FROM users")) == 0
    command.check(config)

    command.downgrade(config, "0001")
    assert inspect(database.engine).get_table_names() == ["alembic_version"]
    command.upgrade(config, "head")
    command.check(config)


def test_email_is_unique_without_case_sensitivity(migrated_database, accounts):
    with migrated_database.engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(
                text("UPDATE users SET email = :email WHERE id = :id"),
                {
                    "email": accounts["administrator"].email.upper(),
                    "id": accounts["patient"].id,
                },
            )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE users SET role = 'unsupported_role' WHERE id = :id",
        "UPDATE users SET role = NULL WHERE id = :id",
        "UPDATE users SET is_active = 2 WHERE id = :id",
        "UPDATE users SET password_hash = NULL WHERE id = :id",
    ],
)
def test_user_constraints(migrated_database, accounts, statement):
    with migrated_database.engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(text(statement), {"id": accounts["patient"].id})


def test_user_defaults_normalization_and_updated_timestamp(migrated_database, accounts):
    from datetime import datetime
    from app.models import User

    with migrated_database.SessionLocal() as session:
        user = session.get(User, accounts["patient"].id)
        assert user.is_active is True
        assert user.created_at is not None
        assert user.updated_at is not None
        original_created_at = user.created_at
        user.updated_at = datetime(2000, 1, 1)
        session.commit()
        user.email = "  Normalized.Patient@EXAMPLE.COM  "
        session.commit()
        session.refresh(user)
        assert user.email == "normalized.patient@example.com"
        assert user.updated_at > datetime(2000, 1, 1)
        assert user.created_at == original_created_at
