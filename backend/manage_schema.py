from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect

from . import models  # noqa: F401
from .database import Base, engine


def main() -> None:
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names()) - {'alembic_version'}
        current = MigrationContext.configure(connection).get_current_revision()
        if tables and current is None:
            differences = compare_metadata(
                MigrationContext.configure(connection, opts={'compare_type': True}),
                Base.metadata,
            )
            if differences:
                raise RuntimeError('Existing database schema differs from the baseline migration; back up and review it before upgrading')
            baseline = True
        else:
            baseline = False
    if baseline:
        command.stamp(config, 'head')
    command.upgrade(config, 'head')
    with engine.connect() as connection:
        differences = compare_metadata(
            MigrationContext.configure(connection, opts={'compare_type': True}),
            Base.metadata,
        )
        if differences:
            raise RuntimeError('Database schema is not in sync with the application models')


if __name__ == '__main__':
    main()
