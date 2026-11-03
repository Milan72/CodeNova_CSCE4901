from logging.config import fileConfig

from alembic import context

from app.database import Base, create_db_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata
migration_engine = create_db_engine()

try:
    if context.is_offline_mode():
        context.configure(
            url=migration_engine.url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )

        with context.begin_transaction():
            context.run_migrations()
    else:
        with migration_engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
finally:
    migration_engine.dispose()
