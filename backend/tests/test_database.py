from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def database(tmp_path, monkeypatch):
    # Set the URL before importing the module that creates the application engine.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    from app import database as database_module

    test_engine = database_module.create_db_engine()
    monkeypatch.setattr(database_module, "engine", test_engine)
    monkeypatch.setattr(database_module, "SessionLocal", sessionmaker(bind=test_engine))
    try:
        yield database_module
    finally:
        test_engine.dispose()


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
    command.upgrade(config, "head")

    assert inspect(database.engine).get_table_names() == ["alembic_version"]
    with database.engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        assert revision == "0001"

    command.check(config)
    command.downgrade(config, "base")
    with database.engine.connect() as connection:
        assert connection.execute(
            text("SELECT COUNT(*) FROM alembic_version")
        ).scalar_one() == 0
