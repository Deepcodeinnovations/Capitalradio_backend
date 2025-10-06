from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
import os
import sys

# Add the project base directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic import context
from app.models.BaseModel import Base
from app.database import get_database_url

# Alembic Config object
config = context.config

# Set the database URL - use a SYNCHRONOUS driver for Alembic
sync_url = get_database_url().replace("mysql+aiomysql", "mysql+pymysql")
config.set_main_option("sqlalchemy.url", sync_url)

# Configure Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a regular (non-async) engine."""
    # Create a SYNCHRONOUS engine - don't use async_engine_from_config
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()