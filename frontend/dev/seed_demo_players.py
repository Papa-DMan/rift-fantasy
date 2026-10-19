"""Fill the stub `player` table with made-up demo players so the draft has
someone to pick before the real lolesports data is hooked up.

Run from the backend folder, against a dev database only:
    cd backend && python ../frontend/dev/seed_demo_players.py
"""
import os
import random
import sys

sys.path.insert(0, os.getcwd())  # run from the backend folder

from sqlalchemy import select

from app import models  # noqa: F401  (register every mapper)
from app.db import SessionLocal
from app.lolesports import Player

TEAMS = ["AUR", "BLZ", "CRN", "DRK", "EMB", "FRS", "GLC", "HVK", "IRN", "JDE", "KRN", "LUM"]
ROLES = ["top", "jungle", "mid", "bottom", "support"]
SYLLABLES = ["ka", "zen", "ry", "vo", "mi", "lux", "tor", "shi", "an", "dro", "ke", "nyx", "pa", "ra", "sol", "fi", "gu", "hex"]

rng = random.Random(7)


def handle() -> str:
    return "".join(rng.choice(SYLLABLES) for _ in range(rng.choice([2, 2, 3]))).capitalize()


with SessionLocal() as db:
    if db.scalar(select(Player.id).limit(1)):
        raise SystemExit("player table already has rows; not seeding")
    used: set[str] = set()
    for team in TEAMS:
        for role in ROLES + ["coach"]:
            name = handle()
            while name in used:
                name = handle()
            used.add(name)
            db.add(Player(name=name, role=role, team_code=team))
    db.commit()
    print(f"seeded {len(used)} demo players")
