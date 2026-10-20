from datetime import timedelta

from db import Game, PlayerGameStats, Round, Series, SeriesStage
from models import Draft
from services.roster import utcnow
from services.scoring import DEFAULT_SCORING_RULES, player_round_points
from tests.test_api import drafted_league


def stats(player_id, game_id, k=0, d=0, a=0, cs=0, vision=0, fb=False):
    # db.py's BIGINT keys don't auto-increment on SQLite, so ids are explicit.
    return PlayerGameStats(id=player_id * 100 + game_id, player_id=player_id, game_id=game_id, kills=k, deaths=d, assists=a, cs=cs,
                           vision_score=vision, first_blood=fb, cs_at_15=0, gold_at_15=0, gold=0,
                           damage=0, objective_steal=0)


def seed_season(session_factory, lid):
    """Draft finished 3 days ago. Round 1 locked before it, round 2 is
    final, round 3 is upcoming. Pro team 1 beats team 2 in each round."""
    now = utcnow()
    with session_factory() as db:
        draft = db.query(Draft).filter_by(league_id=lid).one()
        draft.completed_at = now - timedelta(days=3)
        db.add_all([
            Round(id=1, stage=SeriesStage.PLAY_IN, name="R1", lock_at=now - timedelta(days=5),
                  ends_at=now - timedelta(days=4)),
            Round(id=2, stage=SeriesStage.SWISS, name="R2", lock_at=now - timedelta(days=2),
                  ends_at=now - timedelta(days=1)),
            Round(id=3, stage=SeriesStage.SWISS, name="R3", lock_at=now + timedelta(days=1),
                  ends_at=now + timedelta(days=2)),
            Series(id=1, external_id="s1", team1=1, team2=2, stage=SeriesStage.PLAY_IN),
            Series(id=2, external_id="s2", team1=1, team2=2, stage=SeriesStage.SWISS),
        ])
        db.flush()
        db.add_all([
            Game(id=1, external_id="g1", number=1, series=1, winner_id=1,
                 started_at=now - timedelta(days=5) + timedelta(hours=1),
                 ended_at=now - timedelta(days=5) + timedelta(hours=2)),
            # Starts a few minutes before the lock: still round 2.
            Game(id=2, external_id="g2", number=1, series=2, winner_id=1,
                 started_at=now - timedelta(days=2) - timedelta(minutes=10),
                 ended_at=now - timedelta(days=2) + timedelta(hours=1)),
        ])
        db.flush()
        db.add_all([
            stats(1, 1, k=10),                                            # before the draft: ignored
            stats(1, 2, k=4, d=1, a=6, cs=250, vision=20, fb=True),       # A top
            stats(3, 2, k=1, d=3, a=2, cs=200, vision=10),                # A mid
            stats(9, 2, k=2, cs=100),                                     # A bench (team 2)
            stats(7, 2, d=4, a=1, cs=150),                                # B top (team 2)
        ])
        db.commit()


def test_standings_and_round_detail(client, session_factory):
    s = drafted_league(client)
    a, b, lid, ta, tb, tops, mids = (s[k] for k in ("a", "b", "lid", "ta", "tb", "tops", "mids"))
    assert (tops[0], mids[0], mids[1], tops[1]) == (1, 3, 9, 7)
    seed_season(session_factory, lid)

    r = client.get(f"/leagues/{lid}/standings", headers=b)
    assert r.status_code == 200, r.text
    body = r.json()
    assert [(x["name"], x["status"]) for x in body["rounds"]] == [
        ("R1", "before_draft"), ("R2", "final"), ("R3", "upcoming")]
    # A: top 12-1+12+5+1+2 +3 win +2 for 10 K+A = 36; mid 3-3+4+4+0.5 +3 = 11.5
    # bench player's 8 points don't count. B: top -4+2+3 = 1, loss.
    assert [(t["team_id"], t["total"]) for t in body["teams"]] == [(ta, 47.5), (tb, 1.0)]
    assert body["teams"][0]["rounds"] == {"2": 47.5}
    assert body["scoring_rules"] == DEFAULT_SCORING_RULES

    r = client.get(f"/leagues/{lid}/teams/{ta}/rounds/2", headers=b)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["total"] == 47.5 and d["round"]["status"] == "final"
    lineup = [(x["slot"], x["player"]["id"], x["points"], x["counts"]) for x in d["lineup"]]
    assert lineup == [("top", 1, 36.0, True), ("mid", 3, 11.5, True), ("bench", 9, 8.0, False)]
    assert d["lineup"][0]["games"][0]["breakdown"] == {
        "kills": 12, "deaths": -1, "assists": 12, "cs": 5, "vision_score": 1, "first_blood": 2,
        "win": 3, "ten_kill_assists": 2}

    # The round-2 lineup was stored at first read; a later trade doesn't change it.
    r = client.post(f"/leagues/{lid}/trades", json={"receiver_team_id": tb, "give_player_ids": [mids[1]],
                                                    "receive_player_ids": [s["tops"][2]]}, headers=a)
    assert client.post(f"/leagues/{lid}/trades/{r.json()['id']}/accept", headers=b).status_code == 200
    d = client.get(f"/leagues/{lid}/teams/{ta}/rounds/2", headers=a).json()
    assert [x["player"]["id"] for x in d["lineup"]] == [1, 3, 9]
    # ...but the upcoming round previews the current roster, with no points yet.
    d = client.get(f"/leagues/{lid}/teams/{ta}/rounds/3", headers=a).json()
    assert d["round"]["status"] == "upcoming" and d["total"] == 0
    assert sorted(x["player"]["id"] for x in d["lineup"]) == sorted([1, 3, tops[2]])

    assert client.get(f"/leagues/{lid}/teams/{ta}/rounds/99", headers=a).status_code == 404


def test_commissioner_edits_scoring_rules(client, session_factory):
    s = drafted_league(client)
    a, b, lid = s["a"], s["b"], s["lid"]
    seed_season(session_factory, lid)
    assert client.get(f"/leagues/{lid}", headers=a).json()["scoring_rules"]["kills"] == 3

    assert client.patch(f"/leagues/{lid}", json={"scoring_rules": {"kills": 5}}, headers=b).status_code == 403
    assert client.patch(f"/leagues/{lid}", json={"scoring_rules": {"pentakills": 5}},
                        headers=a).status_code == 422
    assert client.patch(f"/leagues/{lid}", json={"scoring_rules": {"kills": "lots"}},
                        headers=a).status_code == 422
    r = client.patch(f"/leagues/{lid}", json={"scoring_rules": {"kills": 5}}, headers=a)
    assert r.status_code == 200, r.text
    rules = r.json()["scoring_rules"]
    assert rules["kills"] == 5 and rules["assists"] == DEFAULT_SCORING_RULES["assists"]

    # 5 kills between A's starters, 2 more points each.
    totals = {t["team_id"]: t["total"] for t in client.get(f"/leagues/{lid}/standings", headers=a).json()["teams"]}
    assert totals[s["ta"]] == 57.5


def test_coach_scores_team_wins(session_factory):
    with session_factory() as db:
        # Conftest players: 6 per pro team, coach last, so 6 is team 1's coach and 12 is team 2's.
        db.add(Series(id=1, external_id="s1", team1=1, team2=2, stage=SeriesStage.SWISS))
        db.flush()
        now = utcnow()
        games = [Game(id=i, external_id=f"g{i}", number=i, series=1, winner_id=w,
                      started_at=now, ended_at=now) for i, w in ((1, 1), (2, 2), (3, 1))]
        db.add_all(games)
        db.commit()
        pts = player_round_points(db, DEFAULT_SCORING_RULES, games, [6, 12, 18])
        assert (pts[6].points, pts[12].points, pts[18].points) == (20, 10, 0)
        assert [g.points for g in pts[6].games] == [10, 0, 10]
