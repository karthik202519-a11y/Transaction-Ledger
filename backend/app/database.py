"""SQLite connections and explicit transactions; never use implicit driver BEGIN."""
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str):
    engine = create_engine(database_url, connect_args={"check_same_thread": False, "timeout": 10})

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        connection.isolation_level = None
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()

    @event.listens_for(engine, "begin")
    def begin(connection):
        # A write lock is acquired BEFORE reading/checking balances or references.
        # Readers use a deferred snapshot; all writes opt into IMMEDIATE.
        mode = connection.get_execution_options().get("sqlite_begin_mode", "DEFERRED")
        connection.exec_driver_sql(f"BEGIN {mode}")

    return engine


def default_database_url():
    directory = Path(__file__).resolve().parents[1] / "data"
    directory.mkdir(exist_ok=True)
    return f"sqlite:///{(directory / 'ledger.db').as_posix()}"


def initialize(engine):
    from . import models  # noqa: F401: register schema
    with engine.connect() as connection:
        # Driver-level call outside an SQLAlchemy transaction.
        connection.connection.cursor().execute("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(engine)
