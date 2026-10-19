from datetime import timedelta

from app.models import DraftPick
from app.services.roster import roster_fits, utcnow
from tests.conftest import signup

SMALL_ROSTER = {"top": 1, "mid": 1, "bench": 1}  # 3 rounds keeps tests short


def make_league(client, h, **kw):
    body = {"name": "Worlds Buds", "team_name": "Team A", "roster_slots": SMALL_ROSTER, **kw}
    r = client.post("/leagues", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def players_by_role(client, h, lid, role):
    r = client.get(f"/leagues/{lid}/players", params={"position": role}, headers=h)
    return [p["id"] for p in r.json()]


# ---------------------------------------------------------------- auth

def test_register_login_me(client):
    h = signup(client, "daniel")
    r = client.get("/users/me", headers=h)
    assert r.json()["email"] == "daniel@example.com"


def test_duplicate_email_and_bad_password(client):
    signup(client, "daniel")
    r = client.post("/auth/register", json={"email": "DANIEL@example.com",
                                            "password": "whatever123", "display_name": "x"})
    assert r.status_code == 409
    r = client.post("/auth/login", data={"username": "daniel@example.com", "password": "nope"})
    assert r.status_code == 401
    assert client.get("/users/me").status_code == 401
    assert client.get("/users/me", headers={"Authorization": "Bearer junk"}).status_code == 401


# ---------------------------------------------------------------- leagues

def test_create_join_and_privacy(client):
    a, b, c = signup(client, "a"), signup(client, "b"), signup(client, "c")
    league = make_league(client, a, max_teams=2)
    code = league["invite_code"]
    assert league["teams"][0]["is_commissioner"] and code

    r = client.post("/leagues/join", json={"invite_code": code.lower(), "team_name": "Team A"},
                    headers=b)
    assert r.status_code == 409  # team name taken
    r = client.post("/leagues/join", json={"invite_code": code, "team_name": "Team B"}, headers=b)
    assert r.status_code == 201
    assert r.json()["invite_code"] is None  # only the commissioner sees it
    assert client.post("/leagues/join", json={"invite_code": code, "team_name": "B2"},
                       headers=b).status_code == 409  # already in
    assert client.post("/leagues/join", json={"invite_code": code, "team_name": "C"},
                       headers=c).status_code == 409  # full
    assert client.get(f"/leagues/{league['id']}", headers=c).status_code == 404  # not a member
    assert client.post("/leagues/join", json={"invite_code": "NOPE", "team_name": "C"},
                       headers=c).status_code == 404

    assert [l["id"] for l in client.get("/leagues", headers=b).json()] == [league["id"]]
    assert client.patch(f"/leagues/{league['id']}", json={"name": "x"},
                        headers=b).status_code == 403

    # rotating the code kills the old one
    new = client.post(f"/leagues/{league['id']}/invite-code", headers=a).json()["invite_code"]
    assert new != code


# ---------------------------------------------------------------- draft + trades

def drafted_league(client, prefix=""):
    a, b = signup(client, prefix + "a"), signup(client, prefix + "b")
    league = make_league(client, a)
    lid = league["id"]
    tb = client.post("/leagues/join", json={"invite_code": league["invite_code"],
                                            "team_name": "Team B"}, headers=b).json()["my_team_id"]
    ta = league["my_team_id"]

    assert client.post(f"/leagues/{lid}/draft/start", headers=b).status_code == 403
    r = client.post(f"/leagues/{lid}/draft/start", json={"order": [ta, tb]}, headers=a)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["total_rounds"] == 3 and len(d["picks"]) == 6
    assert [p["team_id"] for p in d["picks"]] == [ta, tb, tb, ta, ta, tb]  # snake
    assert client.post("/leagues/join", json={"invite_code": league["invite_code"],
                                              "team_name": "Late"},
                       headers=signup(client, prefix + "late")).status_code == 409

    tops = players_by_role(client, a, lid, "top")
    mids = players_by_role(client, a, lid, "mid")
    jgs = players_by_role(client, a, lid, "jungle")

    def pick(h, pid):
        return client.post(f"/leagues/{lid}/draft/pick", json={"player_id": pid}, headers=h)

    assert pick(b, tops[0]).status_code == 409          # not B's turn
    assert pick(a, tops[0]).status_code == 200          # A: top
    assert pick(b, tops[0]).status_code == 409          # already taken
    assert pick(b, tops[1]).status_code == 200          # B: top
    assert pick(b, tops[2]).status_code == 200          # B: top on bench
    assert pick(b, tops[3]).status_code == 409          # not B's turn
    assert pick(a, mids[0]).status_code == 200          # A: mid
    assert pick(a, mids[1]).status_code == 200          # A: mid on bench
    assert pick(b, tops[3]).status_code == 409          # top + bench both full
    r = pick(b, mids[2])                                # B: mid, last pick
    assert r.status_code == 200
    assert r.json()["status"] == "complete"
    assert client.get(f"/leagues/{lid}", headers=a).json()["status"] == "active"
    assert pick(a, jgs[0]).status_code == 409           # draft over

    roster = client.get(f"/leagues/{lid}/teams/{tb}/roster", headers=a).json()
    assert sorted(e["player"]["id"] for e in roster["players"]) == sorted([tops[1], tops[2], mids[2]])
    return dict(a=a, b=b, lid=lid, ta=ta, tb=tb, tops=tops, mids=mids)


def test_draft_and_trade_flow(client):
    s = drafted_league(client)
    a, b, lid, ta, tb, tops, mids = (s[k] for k in ("a", "b", "lid", "ta", "tb", "tops", "mids"))
    url = f"/leagues/{lid}/trades"

    # A sends mid (bench) for B's bench top: both rosters still fit.
    r = client.post(url, json={"receiver_team_id": tb, "give_player_ids": [mids[1]],
                               "receive_player_ids": [tops[2]]}, headers=a)
    assert r.status_code == 201, r.text
    t1 = r.json()["id"]
    # A competing offer for the same player
    t2 = client.post(url, json={"receiver_team_id": tb, "give_player_ids": [mids[0]],
                                "receive_player_ids": [tops[2]]}, headers=a).json()["id"]
    # Bad offers
    assert client.post(url, json={"receiver_team_id": tb, "give_player_ids": [tops[1]],
                                  "receive_player_ids": [tops[2]]},
                       headers=a).status_code == 409  # A doesn't own tops[1]
    assert client.post(url, json={"receiver_team_id": ta, "give_player_ids": [mids[1]],
                                  "receive_player_ids": [mids[0]]},
                       headers=a).status_code == 422  # self-trade

    assert client.post(f"{url}/{t1}/accept", headers=a).status_code == 403  # proposer can't accept
    r = client.post(f"{url}/{t1}/accept", headers=b)
    assert r.status_code == 200 and r.json()["status"] == "completed"
    assert client.get(f"{url}/{t2}", headers=a).json()["status"] == "cancelled"
    assert client.post(f"{url}/{t1}/reject", headers=b).status_code == 409

    a_roster = client.get(f"/leagues/{lid}/teams/{ta}/roster", headers=a).json()["players"]
    ids = {e["player"]["id"]: e["acquired_via"] for e in a_roster}
    assert ids == {tops[0]: "draft", mids[0]: "draft", tops[2]: "trade"}

    # Reject and cancel
    t3 = client.post(url, json={"receiver_team_id": tb, "give_player_ids": [tops[2]],
                                "receive_player_ids": [mids[1]]}, headers=a).json()["id"]
    assert client.post(f"{url}/{t3}/cancel", headers=b).status_code == 403
    assert client.post(f"{url}/{t3}/reject", headers=b).json()["status"] == "rejected"
    t4 = client.post(url, json={"receiver_team_id": tb, "give_player_ids": [tops[2]],
                                "receive_player_ids": [mids[1]]}, headers=a).json()["id"]
    assert client.post(f"{url}/{t4}/cancel", headers=a).json()["status"] == "cancelled"

    # Uneven trade that would overflow A's roster (4 players, 3 slots)
    assert client.post(url, json={"receiver_team_id": tb, "give_player_ids": [tops[2]],
                                  "receive_player_ids": [tops[1], mids[2]]},
                       headers=a).status_code == 409

    assert len(client.get(url, params={"mine": True}, headers=b).json()) == 4


def test_trade_deadline_and_pre_draft(client):
    a = signup(client, "a")
    league = make_league(client, a)
    r = client.post(f"/leagues/{league['id']}/trades",
                    json={"receiver_team_id": 999, "give_player_ids": [1],
                          "receive_player_ids": [2]}, headers=a)
    assert r.status_code == 409  # league hasn't drafted

    s = drafted_league(client, prefix="d")
    past = (utcnow() - timedelta(days=1)).isoformat()
    assert client.patch(f"/leagues/{s['lid']}", json={"trade_deadline": past},
                        headers=s["a"]).status_code == 200
    r = client.post(f"/leagues/{s['lid']}/trades",
                    json={"receiver_team_id": s["tb"], "give_player_ids": [s["mids"][1]],
                          "receive_player_ids": [s["tops"][2]]}, headers=s["a"])
    assert r.status_code == 409 and "deadline" in r.json()["detail"]


def test_autopick_when_clock_runs_out(client, session_factory):
    a, b = signup(client, "a"), signup(client, "b")
    league = make_league(client, a)
    lid = league["id"]
    client.post("/leagues/join", json={"invite_code": league["invite_code"], "team_name": "B"},
                headers=b)
    client.patch(f"/leagues/{lid}/draft", json={"seconds_per_pick": 30}, headers=a)
    client.post(f"/leagues/{lid}/draft/start", headers=a)

    # Pretend the draft started 75s ago: the first two picks (30s each) have expired.
    with session_factory() as db:
        from app.models import Draft
        d = db.query(Draft).filter_by(league_id=lid).one()
        d.started_at = utcnow() - timedelta(seconds=75)
        db.commit()

    r = client.get(f"/leagues/{lid}/draft", headers=a).json()
    made = [p for p in r["picks"] if p["player_id"] is not None]
    assert len(made) == 2 and all(p["is_autopick"] for p in made)
    assert r["current_pick"] == 3


def test_roster_fits():
    slots = {"top": 1, "mid": 1, "bench": 1}
    assert roster_fits(["top", "mid", "top"], slots)
    assert not roster_fits(["top", "top", "top"], slots)
    assert roster_fits([None], slots)          # unknown position -> bench
    assert not roster_fits([None, "jungle"], slots)
