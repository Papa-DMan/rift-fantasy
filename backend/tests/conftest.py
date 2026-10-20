import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from sqlalchemy import create_engine

import models  # noqa: F401  (register the fantasy tables)
from db import Base, Region
from deps import get_db
from lolesports import Player, PlayerRole, Team
from main import app

ROLES = list(PlayerRole)  # top, jungle, mid, adc, support, coach


@pytest.fixture()
def session_factory():
    # In-memory SQLite by default; set TEST_DATABASE_URL to run against a
    # throwaway Postgres database (its tables are dropped and recreated).
    url = os.getenv("TEST_DATABASE_URL")
    engine = (create_engine(url) if url else
              create_engine("sqlite://", poolclass=StaticPool,
                            connect_args={"check_same_thread": False}))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        # 5 pro teams x 6 roles = 30 players, ids 1..30. Ids are explicit
        # because db.py's BIGINT keys don't auto-increment on SQLite.
        db.add_all([Team(id=t + 1, name=f"T{t}") for t in range(5)])
        db.flush()
        pid = 0
        for t in range(5):
            for role in ROLES:
                pid += 1
                db.add(Player(id=pid, team=t + 1, tag=f"{role.value}{t}", name=f"Player {pid}",
                              position=role, region=Region.LCK))
        db.commit()
    yield factory
    if url:
        Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    def _get_db():
        with session_factory() as db:
            yield db
    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def signup(client, name: str) -> dict:
    email = f"{name}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter2hunter2",
                                            "display_name": name})
    assert r.status_code == 201, r.text
    r = client.post("/auth/login", data={"username": email, "password": "hunter2hunter2"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
