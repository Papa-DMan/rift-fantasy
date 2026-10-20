"""The scraper against a fake lolesports API: one completed Bo1 between pro
teams 1 (blue) and 2 (red), plus one series that hasn't started."""
from datetime import datetime, timedelta, timezone

import pytest

import scraper
from db import Game, PlayerGameStats, Round, Series, SeriesStage
from models import Draft, LineupSlot
from services.roster import as_utc
from tests.test_api import drafted_league

NOW = datetime.now(timezone.utc).replace(microsecond=0)
START = NOW - timedelta(hours=3)
END = START + timedelta(minutes=31, seconds=7)
# (time into the game, killer participantId, victim participantId)
KILLS = [(timedelta(minutes=4, seconds=12), 3, 8), (timedelta(minutes=9), 6, 2),
         (timedelta(minutes=22), 3, 9), (timedelta(minutes=30), 4, 10)]
ROLES = ["top", "jungle", "mid", "bottom", "support"]


def stats_at(t: datetime) -> dict[int, dict]:
    e = min(t, END) - START
    out = {}
    for pid in range(1, 11):
        out[pid] = {"participantId": pid, "level": 1, "currentHealth": 1, "maxHealth": 1,
                    "kills": sum(1 for at, k, _ in KILLS if at <= e and k == pid),
                    "deaths": sum(1 for at, _, v in KILLS if at <= e and v == pid),
                    "assists": int(e.total_seconds() // 600),
                    "creepScore": int(e.total_seconds() // 6), "totalGold": 500 + int(e.total_seconds() * 6)}
    return out


def frame(t: datetime, state: str) -> dict:
    p = stats_at(t)
    blue_won = t >= END
    return {"rfc460Timestamp": t.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "gameState": state,
            "blueTeam": {"totalGold": 1, "inhibitors": 2 if blue_won else 0, "towers": 9, "barons": 1,
                         "totalKills": 3, "dragons": [], "participants": [p[i] for i in range(1, 6)]},
            "redTeam": {"totalGold": 1, "inhibitors": 0, "towers": 3, "barons": 0, "totalKills": 1,
                        "dragons": [], "participants": [p[i] for i in range(6, 11)]}}


METADATA = {"patchVersion": "16.20", **{
    side: {"esportsTeamId": ext, "participantMetadata": [
        {"participantId": base + i + 1, "summonerName": f"{code} {role if role != 'bottom' else 'adc'}{n}",
         "championId": "Ahri", "role": role} for i, role in enumerate(ROLES)]}
    for side, ext, code, n, base in (("blueTeamMetadata", "ext-1", "T0", 0, 0),
                                     ("redTeamMetadata", "ext-2", "T1", 1, 5))}}


class FakeApi:
    def __init__(self, empty_after_end=False):
        self.calls = 0
        self.empty_after_end = empty_after_end

    def schedule(self, league_ids):
        team = lambda n, outcome=None: {"name": f"T{n}", "code": f"T{n}", "image": "",  # noqa: E731
                                        "result": {"outcome": outcome, "gameWins": 1 if outcome == "win" else 0}}
        return [
            {"startTime": (START - timedelta(minutes=10)).isoformat(), "blockName": "Swiss", "state": "completed",
             "type": "match", "match": {"id": "m1", "teams": [team(0, "win"), team(1, "loss")]}},
            {"startTime": (NOW + timedelta(days=1)).isoformat(), "blockName": "Quarterfinals", "state": "unstarted",
             "type": "match", "match": {"id": "m2", "teams": [team(2), team(3)]}},
            {"startTime": "2025-10-01T00:00:00Z", "state": "completed", "type": "match",   # last year's Worlds
             "match": {"id": "old", "teams": [team(0), team(1)]}},
        ]

    def event_details(self, match_id):
        assert match_id == "m1"
        return {"match": {"teams": [{"id": "ext-1", "name": "T0", "code": "T0"},
                                    {"id": "ext-2", "name": "T1", "code": "T1"}],
                          "games": [{"id": "g1", "number": 1, "state": "completed"},
                                    {"id": "g2", "number": 2, "state": "unneeded"}]}}

    def window(self, game_id, at=None):
        self.calls += 1
        now = scraper.utcnow()
        if at is None:  # the live feed's "latest" view
            at = min(now, END) - timedelta(seconds=10)
        at = scraper.parse_ts(scraper.api_time(at))
        if at < START or at > now:
            return None
        if at >= END:
            return None if self.empty_after_end else {"gameMetadata": METADATA, "frames": [frame(END, "finished")]}
        frames = [frame(at + timedelta(seconds=s), "in_game") for s in (0, 5) if at + timedelta(seconds=s) < END]
        if at + timedelta(seconds=10) > END:
            frames.append(frame(END, "finished"))
        return {"gameMetadata": METADATA, "frames": frames}

    def details(self, game_id, at=None):
        return {"frames": [{"rfc460Timestamp": "", "participants": [
            {"participantId": pid, "wardsPlaced": pid * 3, "wardsDestroyed": 2} for pid in range(1, 11)]}]}


@pytest.fixture()
def db(session_factory):
    with session_factory() as s:
        yield s


@pytest.mark.parametrize("empty_after_end", [False, True])
def test_scrape_completed_game(db, empty_after_end):
    api = FakeApi(empty_after_end)
    assert scraper.run_once(db, api) is False

    series = {s.external_id: s for s in db.query(Series)}
    assert set(series) == {"m1", "m2"}
    assert (series["m1"].team1, series["m1"].team2, series["m1"].stage) == (1, 2, SeriesStage.SWISS)
    assert series["m2"].stage == SeriesStage.KNOCKOUT
    (game,) = db.query(Game).all()
    assert (game.external_id, game.number, game.series, game.winner_id) == ("g1", 1, series["m1"].id, 1)
    assert abs(as_utc(game.started_at) - START) <= timedelta(seconds=10)
    assert abs(as_utc(game.ended_at) - END) <= timedelta(seconds=10)

    rows = {r.player_id: r for r in db.query(PlayerGameStats)}
    # conftest: team 1 is players 1-6 (top..coach), team 2 is 7-12; coaches have no stat line.
    assert sorted(rows) == [1, 2, 3, 4, 5, 7, 8, 9, 10, 11]
    mid = rows[3]
    assert (mid.kills, mid.deaths, mid.first_blood, mid.vision_score) == (2, 0, True, 11)
    assert 150 <= mid.cs_at_15 <= 152 and 5900 <= mid.gold_at_15 <= 5960  # 15:00, give or take a frame
    assert mid.cs in (310, 311) and not rows[1].first_blood
    assert rows[9].deaths == 1  # red mid gave up first blood

    # A second pass changes nothing and doesn't re-read the finished game.
    before = api.calls
    scraper.run_once(db, api)
    assert api.calls == before
    assert db.query(Game).count() == 1 and db.query(PlayerGameStats).count() == 10


def test_live_game_then_final(db, monkeypatch):
    api = FakeApi()
    monkeypatch.setattr(scraper, "utcnow", lambda: START + timedelta(minutes=20))
    assert scraper.run_once(db, api) is True
    (game,) = db.query(Game).all()
    assert game.ended_at is None and game.winner_id is None and game.started_at is not None
    assert db.get(PlayerGameStats, db.query(PlayerGameStats.id).filter_by(player_id=3).scalar()).kills == 1

    monkeypatch.setattr(scraper, "utcnow", lambda: NOW)
    scraper.run_once(db, api)
    db.refresh(game)
    assert game.ended_at is not None and game.winner_id == 1
    assert db.query(PlayerGameStats).filter_by(player_id=3).one().kills == 2


def test_scrape_feeds_fantasy_points(client, session_factory):
    s = drafted_league(client)  # team A starts players 1 (top) and 3 (mid)
    with session_factory() as db:
        db.query(Draft).filter_by(league_id=s["lid"]).one().completed_at = START - timedelta(days=1)
        db.add(Round(id=1, stage=SeriesStage.SWISS, name="Swiss 1", lock_at=START - timedelta(minutes=10),
                     ends_at=START + timedelta(hours=2)))
        db.commit()
        scraper.run_once(db, FakeApi())
        cached = {r.player_id: r.points for r in db.query(LineupSlot).filter_by(team_id=s["ta"])}
    standings = client.get(f"/leagues/{s['lid']}/standings", headers=s["a"]).json()
    a_total = next(t["total"] for t in standings["teams"] if t["team_id"] == s["ta"])
    assert a_total > 0 and a_total == pytest.approx(cached[1] + cached[3])
