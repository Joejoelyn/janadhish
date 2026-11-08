"""Smoke check: migration startup must not stamp an incompatible database."""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / 'mismatched.db'
    os.environ['DATABASE_URL'] = f'sqlite:///{path.as_posix()}'
    from backend.manage_schema import main

    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE orders (id INTEGER PRIMARY KEY)')
        db.execute('INSERT INTO orders (id) VALUES (42)')

    try:
        main()
    except RuntimeError as exc:
        assert 'differs from the baseline' in str(exc)
    else:
        raise AssertionError('Mismatched schema was accepted')

    with sqlite3.connect(path) as db:
        assert db.execute('SELECT id FROM orders').fetchone() == (42,)
        assert db.execute("SELECT name FROM sqlite_master WHERE name='alembic_version'").fetchone() is None

print('Mismatched schema was rejected without changing its data')
