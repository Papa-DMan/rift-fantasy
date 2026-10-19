import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db, make_engine
from app.lolesports import Player
from app.main import app

ROLES = ["top", "jungle", "mid", "adc", "support", "coach"]


@pytest.fixture()
def session_factory():
    # In-memory SQLite by default; set TEST_DATABASE_URL to run against a
    # throwaway Postgres database (its tables are dropped and recreated).
    url = os.getenv("TEST_DATABASE_URL")
    engine = make_engine(url) if url else make_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        # 5 pro teams x 6 roles = 30 players, ids 1..30
        for t in range(5):
            for role in ROLES:
                db.add(Player(name=f"{role}{t}", role=role, team_code=f"T{t}"))
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
