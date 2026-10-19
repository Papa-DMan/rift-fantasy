from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

import db as esports_db
from app.config import settings


class Base(DeclarativeBase):
    # Same MetaData as the lolesports models in ../db.py (player, round, team,
    # game, ...), so the fantasy tables' foreign keys resolve and create_all
    # builds everything. A separate registry keeps the two `Team` classes
    # (pro team vs fantasy team) from clashing by name.
    metadata = esports_db.Base.metadata


def make_engine(url: str, **kwargs) -> Engine:
    if url.startswith("sqlite"):
        kwargs.setdefault("connect_args", {"check_same_thread": False})
    else:
        kwargs.setdefault("pool_pre_ping", True)  # survive Postgres restarts / idle drops
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        # SQLite ignores foreign keys (and so ON DELETE CASCADE) unless asked.
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    return engine


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db
