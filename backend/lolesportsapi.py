from typing import Literal

from pydantic import BaseModel, Field

class Team(BaseModel):
    code : str
    image : str
    name : str
    id : str | None = Field(default=None)
    result : TeamResult | None = Field(default=None)

class TeamResult(BaseModel):
    gameWins : int

class ExtendedGame(BaseModel):
    id : str
    state : Literal["completed", "unstarted", "inProgress", "unneeded"]
    number : Literal[1, 2, 3, 4, 5]
    vods : list[ExtendedVod]
    teams : list[CustomTeam]

class ExtendedVod(BaseModel):
    parameter : str
    locale : str
    provider : str
    offset : int

class CustomTeam(BaseModel):
    id : str
    side : Literal["blue", "red"] | None

class BaseStrategy(BaseModel):
    count : Literal[1, 3, 5]

class League(BaseModel):
    name : str
    slug : str
    id : str | None = Field(default=None)
    image : str | None = Field(default=None)
    priority : int | None = Field(default=None)


class Match(BaseModel):
    teams : list[Team]
    id : str | None = Field(default=None)
    games : list[ExtendedGame] | None = Field(default=None)
    strategy : BaseStrategy

class Event(BaseModel):
    match : Match
    id : str
    type : Literal["match", "show"]
    league : League
    streams : list[ExtendedVod] | None = Field(default=None)

class ScheduleEvent(BaseModel):
    startTime : str
    blockName : str | None = Field(default=None)
    match : Match
    state : Literal["completed", "unstarted", "inProgress"]
    type : Literal["match", "show"]
    id : str | None = Field(default=None)
    league : League


class Schedule(BaseModel):
    events : list[Event] | None = Field(default=None)

class Pages(BaseModel):
    older : str | None = Field(default=None)
    newer : str | None = Field(default=None)

class PaginatedSchedule(BaseModel):
    updated : str | None = Field(default=None)
    pages : Pages
    events : list[ScheduleEvent]


class ParticipantMetadata(BaseModel):
    participantId : Literal[1,2,3,4,5,6,7,8,9,10]
    summonerName : str
    championId : str
    role : Literal["top", "jungle", "mid", "bottom", "support"]
    esportsPlayerId : str | None = Field(default=None)

class TeamMetadata(BaseModel):
    esportsTeamId: str
    participantMetadata : list[ParticipantMetadata]

class GameMetadata(BaseModel):
    patchVersion : str
    blueTeamMetadata : TeamMetadata
    redTeamMetadata : TeamMetadata

class ParticipantStats(BaseModel):
    participantId : Literal[1,2,3,4,5,6,7,8,9,10]
    level : int
    kills : int
    deaths : int
    assists : int
    creepScore : int
    totalGold : int
    currentHealth : int
    maxHealth : int

class ExtendedParticipantStats(BaseModel):
    participantId : Literal[1,2,3,4,5,6,7,8,9,10]
    level : int
    kills : int
    deaths : int
    assists : int
    creepScore : int
    totalGold : int
    currentHealth : int
    maxHealth : int
    totalGoldEarned : int
    killParticipation : float
    championDamageShare : float
    wardsPlaced : int
    wardsDestroyed : int
    attackDamage : int
    abilityPower : int
    criticalChance : float
    attackSpeed : int
    lifeSteal : int
    armor : int
    magicResistance : int
    tenacity : float
    items : list[int]

class TeamStats(BaseModel):
    totalGold : int
    inhibitors : int
    towers : int
    barons : int
    totalKills : int
    dragons : list[Literal["ocean", "mountain", "infernal", "cloud", "elder", "hextech", "chemtech"]]
    participants: list[ParticipantStats]

class WindowFrame(BaseModel):
    rfc460Timestamp : str
    gameState : Literal["in_game", "finished"]
    blueTeam : TeamStats
    redTeam : TeamStats

class DetailFrame(BaseModel):
    rfc460Timestamp : str
    participants: list[ExtendedParticipantStats]

class Window(BaseModel):
    esportsGameId : str
    esportsMatchId : str
    gameMetadata: GameMetadata
    frames : list[WindowFrame]

class DetailWindow(BaseModel):
    frames: list[DetailFrame]

class Tournament(BaseModel):
    endDate : str
    id : str
    slug : str
    startDate : str

class League(BaseModel):
    tournaments : list[Tournament]

class Ranking(BaseModel):
    ordinal : int
    teams : list[Team]

class Section(BaseModel):
    name : str
    matches : list[Match]
    rankings : list[Ranking]

class Stage(BaseModel):
    name : str
    type : Literal["groups", "bracket"]
    slug : str
    sections : list[Section]