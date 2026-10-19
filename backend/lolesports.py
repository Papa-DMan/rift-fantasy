from datetime import datetime, timedelta, timezone
import json
import os
import requests
import lolesportsapi

WORLDS_LEAGUE_ID=98767975604431411

def log(*kwargs):
    if os.environ.get("DEBUG"):
        print(kwargs)

def getEventDetails(match_id : str):
    url = "https://esports-api.lolesports.com/persisted/gw/getEventDetails"

    headers = {
        "x-api-key": "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
    }

    params = {
        "hl" : "en-US",
        "id" : match_id
    }

    try :
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        log(json.dumps(data))

        if data['data']['event'] != None:
            orm = lolesportsapi.Event(**data['data']['event'])
            return orm
        return None
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err}")
    except requests.exceptions.RequestException as err:
        print(f"An error occurred: {err}")


def getLive() -> lolesportsapi.Schedule:
    url = "https://esports-api.lolesports.com/persisted/gw/getLive"
    headers = {
        "x-api-key": "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
    }
    params = {
        "hl" : "en-US"
    }
    try :
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        orm = lolesportsapi.Schedule(**data['data']['schedule'])
        log(json.dumps(data))
        return orm
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err}")
    except requests.exceptions.RequestException as err:
        print(f"An error occurred: {err}")

def getSchedule(leagueId : list[int] | None = None, pageToken : str | None = None):
    url = "https://esports-api.lolesports.com/persisted/gw/getSchedule"
    headers = {
        "x-api-key": "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
    }
    params = {
        "hl" : "en-US",
        "leagueId" : leagueId,
        "pageToken" : pageToken,
    }
    more_pages = True
    events : list[lolesportsapi.ScheduleEvent] = []
    while more_pages:
        try :
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            log(json.dumps(data))
            orm = lolesportsapi.PaginatedSchedule(**data['data']['schedule'])
            events.extend(orm.events)
            params["pageToken"] = orm.pages.newer
            if orm.pages.newer == None:
                more_pages = False
        except requests.exceptions.HTTPError as err:
            print(f"HTTP error occurred: {err}")
        except requests.exceptions.RequestException as err:
            print(f"An error occurred: {err}")
    return events

def getLeagues():
    url = "https://esports-api.lolesports.com/persisted/gw/getLeagues"
    headers = {
        "x-api-key": "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
    }
    params = {
        "hl" : "en-US"
    }

    try: 
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        log(json.dumps(data))
        orms = [lolesportsapi.League(**l) for l in data['data']['leagues']]
        return orms
    except requests.exceptions.HTTPError as err:
            print(f"HTTP error occurred: {err}")
    except requests.exceptions.RequestException as err:
        print(f"An error occurred: {err}")


def getWindow(gameId : str, startingTime : datetime | None = None):
    url = f"https://feed.lolesports.com/livestats/v1/window/{gameId}"
    headers = {
        "x-api-key": "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
    }
    params = {
        "hl" : "en-US",
        "startingTime" : to_api_time(startingTime)
    }
    try: 
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        log(json.dumps(data))
        orm = lolesportsapi.Window(**data)
        return orm
    except requests.exceptions.HTTPError as err:
            print(f"HTTP error occurred: {err}")
    except requests.exceptions.RequestException as err:
        print(f"An error occurred: {err}")


def getDetails(gameId : str, startingTime : datetime | None = None, participantIds : str | None = None):
    url = f"https://feed.lolesports.com/livestats/v1/details/{gameId}"
    headers = {
        "x-api-key": "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
    }
    params = {
        "startingTime" : to_api_time(startingTime)
    }
    try: 
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        log(json.dumps(data))
        orms = [lolesportsapi.DetailFrame(**f) for f in data['frames']]
        return orms
    except requests.exceptions.HTTPError as err:
            print(f"HTTP error occurred: {err}")
    except requests.exceptions.RequestException as err:
        print(f"An error occurred: {err}")



def getTournamentsForLeague(leagueId : str | None = None):
    url = f"https://esports-api.lolesports.com/persisted/gw/getTournamentsForLeague"
    headers = {
        "x-api-key": "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
    }
    params = {
        "hl" : "en-US",
        "leagueId" : leagueId
    }
    try: 
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        log(json.dumps(data))
        orms = [lolesportsapi.League(**l) for l in data['data']['leagues']]
        return orms
    except requests.exceptions.HTTPError as err:
            print(f"HTTP error occurred: {err}")
    except requests.exceptions.RequestException as err:
        print(f"An error occurred: {err}")

def getStandings(tournamentId : str):
    url = f"https://esports-api.lolesports.com/persisted/gw/getStandings"
    headers = {
            "x-api-key": "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
        }
    params = {
        "hl" : "en-US",
        "tournamentId" : tournamentId
    }
    try: 
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        log(json.dumps(data))
        orms = [lolesportsapi.Stage(**s) for s in data['standings']]
        return orms
    except requests.exceptions.HTTPError as err:
            print(f"HTTP error occurred: {err}")
    except requests.exceptions.RequestException as err:
        print(f"An error occurred: {err}")
 


def to_api_time(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    dt = dt - timedelta(seconds=dt.second % 10)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
