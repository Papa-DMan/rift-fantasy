from datetime import datetime, timezone
import enum
import os
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from sqlalchemy import  CheckConstraint, Index, create_engine, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, scoped_session, Session

class DBConfig(BaseModel):
    host: str
    port: int
    database: str
    user: str
    password : str = Field(default_factory=lambda: os.environ.get("POSTGRES_PASSWORD", ""))


class DBManager:
    def __init__(self, conf : DBConfig):
        self.config = conf
        self.db_url = f"postgresql+psycopg://{self.config.user}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}"

        self.engine = None
        self._session = None

    def get_session(self) -> Session:
        if self.engine is None:
            self.engine = create_engine(self.db_url)
        if self._session is None:
            self._session = scoped_session(sessionmaker(bind=self.engine))
        
        return self._session()
    
    def disconnect(self):
        if self._session is not None:
            self._session.remove()
            self._session = None
        
        if self.engine is not None:
            self.engine.dispose()
            self.engine = None
            
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def create_all(self):
        if self.engine is None:
            self.get_session()
        Base.metadata.create_all(self.engine)



from sqlalchemy import (
    Boolean, ForeignKey, Integer, Numeric, Enum, BigInteger, String, DateTime, UniqueConstraint, VARBINARY
)

class Base(DeclarativeBase):
    pass

class PlayerRole(enum.Enum):
    TOP = "top"
    JUNGLE = "jungle"
    MID = "mid"
    ADC = "adc"
    SUPPORT = "support"
    COACH = "coach"

class Region(enum.Enum):
    LCK = "lck"
    LCP = "lcp"
    LCS = "lcs"
    LEC = "lec"
    LPL = "lpl"
    CBLOL = "cblol"

class FeedSource(enum.Enum):
    WINDOW = "window"
    DETAILS = "details"

class SeriesStage(enum.Enum):
    PLAY_IN = "playin"
    SWISS = "swiss"
    KNOCKOUT = "knockout"


# JSONB on Postgres, plain JSON elsewhere (SQLite for tests).
JSONType = JSON().with_variant(JSONB(), "postgresql")

def pk() -> Mapped[int]:
    return mapped_column(BigInteger, primary_key=True)

def created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())

class Game(Base):
    __tablename__ = "game"
    id : Mapped[int] = pk()
    external_id : Mapped[str] = mapped_column(String, unique=True)
    number : Mapped[int] = mapped_column(Integer)
    series : Mapped[int] = mapped_column(ForeignKey("series.id"))
    winner_id : Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=True)
    started_at : Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at : Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class Series(Base):
    __tablename__ = "series"
    id : Mapped[int] = pk()
    external_id : Mapped[str] = mapped_column(String, unique=True)
    team1 : Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=True)
    team2 : Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=True)
    stage : Mapped[SeriesStage] = mapped_column(Enum(SeriesStage))

class Team(Base):
    __tablename__ = "team"
    id : Mapped[int] = pk()
    name : Mapped[str] = mapped_column(String(64))

class Player(Base):
    __tablename__ = "player"
    id : Mapped[int] = pk()
    team : Mapped[int] = mapped_column(ForeignKey("team.id"))
    tag : Mapped[str] = mapped_column(String(32))
    name : Mapped[str] = mapped_column(String(64))
    position : Mapped[PlayerRole] = mapped_column(Enum(PlayerRole))
    region : Mapped[Region] = mapped_column(Enum(Region))

class PlayerGameStats(Base):
    __tablename__ = "player_game_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "game_id"),
    )
    id : Mapped[int] = pk()
    player_id : Mapped[int] = mapped_column(ForeignKey("player.id"))
    game_id : Mapped[int] = mapped_column(ForeignKey("game.id"))
    cs_at_15 : Mapped[int] = mapped_column(Integer)
    gold_at_15: Mapped[int] = mapped_column(Integer)
    first_blood: Mapped[bool] = mapped_column(Boolean)
    kills : Mapped[int] = mapped_column(Integer)
    deaths : Mapped[int] = mapped_column(Integer)
    assists : Mapped[int] = mapped_column(Integer)
    cs : Mapped[int] = mapped_column(Integer)
    gold : Mapped[int] = mapped_column(Integer)
    damage : Mapped[int] = mapped_column(Integer)
    vision_score : Mapped[int] = mapped_column(Integer)
    objective_steal : Mapped[int] = mapped_column(Integer)

class PlayerGameScore(Base):
    __tablename__ = "player_game_scores"
    __table_args__ = (
        UniqueConstraint("player_id", "game_id", "scoring_version"),
    )
    id : Mapped[int] = pk()
    player_id : Mapped[int] = mapped_column(ForeignKey("player.id"))
    game_id : Mapped[int] = mapped_column(ForeignKey("game.id"))
    scoring_version : Mapped[int] = mapped_column(Integer)
    points : Mapped[float] = mapped_column(Numeric)
    breakdown : Mapped[dict] = mapped_column(JSONType)

class Feed(Base):
    __tablename__ = "feed"
    __table_args__ = (
        UniqueConstraint("game_id", "source", "frame_ts"),
    )
    id : Mapped[int] = pk()
    game_id : Mapped[int] = mapped_column(ForeignKey("game.id"))
    source : Mapped[FeedSource] = mapped_column(Enum(FeedSource))
    frame_ts : Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data : Mapped[dict] = mapped_column(JSONType)


class Round(Base):
    __tablename__ = "round"
    id : Mapped[int] = pk()
    stage : Mapped[SeriesStage] = mapped_column(Enum(SeriesStage))
    name : Mapped[str] = mapped_column(String(64))
    lock_at : Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at : Mapped[datetime] = mapped_column(DateTime(timezone=True))





# Fantasy-side tables (users, leagues, teams, rosters, lineups, drafts, trades)
# live in app/models.py. They share this Base's MetaData, so their foreign
# keys to player.id and round.id resolve against the tables above.




def seed(session : Session) -> None:
    for batch in (SCHEDULE, TEAMS, PLAYERS):
        session.add_all(batch)
        session.flush()
    create_games(session)
    session.commit()
    reset_sequences(session)

def reset_sequences(session : Session) -> None:
    for table in ("round", "team", "player", "series"):
        session.execute(text(
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1))"
        ))
    session.commit()

gamecount = 0
def next_game():
    global gamecount
    gamecount += 1
    return gamecount

def create_games(session : Session):
    serieses : list[Series] = []
    games : list[Game] = []
    from lolesports import getSchedule, WORLDS_LEAGUE_ID, getEventDetails
    schedule_events = getSchedule([WORLDS_LEAGUE_ID])
    schedule_events = [e for e in schedule_events if datetime.fromisoformat(e.startTime) > datetime(2026, 1, 1, tzinfo=timezone.utc)]
    for i, event in enumerate(schedule_events, start=1):
        stage = SeriesStage.PLAY_IN
        if event.blockName.lower() == "swiss":
            stage = SeriesStage.SWISS
        elif "finals" in event.blockName.lower():
            stage = SeriesStage.KNOCKOUT
        series = Series(id=i, external_id = event.match.id, stage=stage)
        details = getEventDetails(event.match.id)
        for j, gameDetails in enumerate(details.match.games, start=1):
            game = Game(id = next_game(), external_id = gameDetails.id, number = j, series = i)
            games.append(game)
        serieses.append(series)

    session.add_all(serieses)
    session.commit()
    session.add_all(games)
    session.commit()
    session.flush()
    

SCHEDULE = [
    Round(
        id=1,
        stage=SeriesStage.PLAY_IN,
        lock_at = datetime.strptime("2026-10-15 14:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        ends_at = datetime.strptime("2026-10-16 00:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        name="Play-In Round 1"
    ),
    Round(
        id=2,
        stage=SeriesStage.PLAY_IN,
        # Oct 16 has two series (14:00 and 19:00 Detroit); lock before the first one
        lock_at = datetime.strptime("2026-10-16 14:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        ends_at = datetime.strptime("2026-10-17 00:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        name="Play-In Round 2"
    ),
    Round(
        id=3,
        stage=SeriesStage.PLAY_IN,
        lock_at = datetime.strptime("2026-10-17 14:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        ends_at = datetime.strptime("2026-10-18 00:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        name="Play-In Round 3"
    ),
    Round(
        id=4,
        stage=SeriesStage.PLAY_IN,
        # Play-In final is Sunday Oct 18 at 14:00 Detroit (was a copy of Round 3's dates)
        lock_at = datetime.strptime("2026-10-18 14:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        ends_at = datetime.strptime("2026-10-19 00:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        name="Play-In Round 4"
    ),
    Round(
        id=5,
        stage=SeriesStage.SWISS,
        lock_at = datetime.strptime("2026-10-23 13:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        ends_at = datetime.strptime("2026-10-24 00:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        name="Swiss Round 1"
    ),
    Round(
        id=6,
        stage=SeriesStage.SWISS,
        lock_at = datetime.strptime("2026-10-24 13:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        ends_at = datetime.strptime("2026-10-25 00:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        name="Swiss Round 2"
    ),
    Round(
        id=7,
        stage=SeriesStage.SWISS,
        lock_at = datetime.strptime("2026-10-25 13:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        ends_at = datetime.strptime("2026-10-27 00:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        name="Swiss Round 3"
    ),
    Round(
        id=8,
        stage=SeriesStage.SWISS,
        lock_at = datetime.strptime("2026-10-28 13:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        ends_at = datetime.strptime("2026-10-31 00:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        name="Swiss Round 4"
    ),
    Round(
        id=9,
        stage=SeriesStage.SWISS,
        lock_at = datetime.strptime("2026-10-31 13:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        ends_at = datetime.strptime("2026-11-01 00:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        name="Swiss Round 5"
    ),
    Round(
        id=10,
        stage=SeriesStage.KNOCKOUT,
        lock_at = datetime.strptime("2026-11-03 17:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        ends_at = datetime.strptime("2026-11-07 00:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        name="Quarterfinals"
    ),
    Round(
        id=11,
        stage=SeriesStage.KNOCKOUT,
        lock_at = datetime.strptime("2026-11-07 17:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        ends_at = datetime.strptime("2026-11-09 00:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        name="Semifinals"
    ),
    Round(
        id=12,
        stage=SeriesStage.KNOCKOUT,
        lock_at = datetime.strptime("2026-11-14 14:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        ends_at = datetime.strptime("2026-11-15 00:00", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/Detroit")),
        name="Finals"
    ),
]

 
GEN, HLE, T1, DK, AL, BLG, TES, IG, G2, MKOI, KC, TL, LYON, C9, TSW, CFO, MVK, LOS, FUR = range(1, 20)
 
TEAMS = [
    Team(id=GEN,  name="Gen.G"),                             # LCK #1
    Team(id=HLE,  name="Hanwha Life Esports"),               # LCK #2 (MSI 2026 champion)
    Team(id=T1,   name="T1"),                                # LCK #3
    Team(id=DK,   name="Dplus Kia"),                         # LCK #4
    Team(id=AL,   name="Anyone's Legend"),                   # LPL #1
    Team(id=BLG,  name="Bilibili Gaming"),                   # LPL #2
    Team(id=TES,  name="TOP Esports"),                       # LPL #3
    Team(id=IG,   name="Shanghai Invictus Gaming Meituan"),  # LPL #4
    Team(id=G2,   name="G2 Esports"),                        # LEC #1
    Team(id=MKOI, name="Movistar KOI"),                      # LEC #2
    Team(id=KC,   name="Karmine Corp"),                      # LEC #3 - Play-In
    Team(id=TL,   name="Team Liquid Alienware"),             # LCS #1
    Team(id=LYON, name="LYON"),                              # LCS #2
    Team(id=C9,   name="Cloud9 Kia"),                        # LCS #3 - Play-In
    Team(id=TSW,  name="Team Secret Whales"),                # LCP #1
    Team(id=CFO,  name="CTBC Flying Oyster"),                # LCP #2
    Team(id=MVK,  name="MVK Esports"),                       # LCP #3 - Play-In
    Team(id=LOS,  name="LOS"),                               # CBLOL #1
    Team(id=FUR,  name="FURIA"),                             # CBLOL #2 - Play-In
]
 
# Each team: starting five, head coach, then registered substitutes (marked "# sub").
PLAYERS = [
    # ---------------------------------------------------------------- Gen.G
    Player(id=1,   team=GEN,  tag="Kiin",        name="Kim Gi-in",                  position=PlayerRole.TOP,     region=Region.LCK),
    Player(id=2,   team=GEN,  tag="Canyon",      name="Kim Geon-bu",                position=PlayerRole.JUNGLE,  region=Region.LCK),
    Player(id=3,   team=GEN,  tag="Chovy",       name="Jeong Ji-hoon",              position=PlayerRole.MID,     region=Region.LCK),
    Player(id=4,   team=GEN,  tag="Ruler",       name="Park Jae-hyuk",              position=PlayerRole.ADC,     region=Region.LCK),
    Player(id=5,   team=GEN,  tag="Duro",        name="Joo Min-kyu",                position=PlayerRole.SUPPORT, region=Region.LCK),
    Player(id=6,   team=GEN,  tag="Ryu",         name="Ryu Sang-wook",              position=PlayerRole.COACH,   region=Region.LCK),
    # ---------------------------------------------------------------- Hanwha Life Esports
    Player(id=7,   team=HLE,  tag="Zeus",        name="Choi Woo-je",                position=PlayerRole.TOP,     region=Region.LCK),
    Player(id=8,   team=HLE,  tag="Kanavi",      name="Seo Jin-hyeok",              position=PlayerRole.JUNGLE,  region=Region.LCK),
    Player(id=9,   team=HLE,  tag="Zeka",        name="Kim Geon-woo",               position=PlayerRole.MID,     region=Region.LCK),
    Player(id=10,  team=HLE,  tag="Gumayusi",    name="Lee Min-hyeong",             position=PlayerRole.ADC,     region=Region.LCK),
    Player(id=11,  team=HLE,  tag="Delight",     name="Yoo Hwan-joong",             position=PlayerRole.SUPPORT, region=Region.LCK),
    Player(id=12,  team=HLE,  tag="Homme",       name="Yoon Sung-young",            position=PlayerRole.COACH,   region=Region.LCK),
    # ---------------------------------------------------------------- T1
    Player(id=13,  team=T1,   tag="Doran",       name="Choi Hyeon-joon",            position=PlayerRole.TOP,     region=Region.LCK),
    Player(id=14,  team=T1,   tag="Oner",        name="Mun Hyeon-jun",              position=PlayerRole.JUNGLE,  region=Region.LCK),
    Player(id=15,  team=T1,   tag="Faker",       name="Lee Sang-hyeok",             position=PlayerRole.MID,     region=Region.LCK),
    Player(id=16,  team=T1,   tag="Peyz",        name="Kim Su-hwan",                position=PlayerRole.ADC,     region=Region.LCK),
    Player(id=17,  team=T1,   tag="Keria",       name="Ryu Min-seok",               position=PlayerRole.SUPPORT, region=Region.LCK),
    Player(id=18,  team=T1,   tag="Tom",         name="Im Jae-hyeon",               position=PlayerRole.COACH,   region=Region.LCK),  # interim HC; kkOma on leave since Mar 2026
    # ---------------------------------------------------------------- Dplus Kia
    Player(id=19,  team=DK,   tag="Siwoo",       name="Jeon Si-woo",                position=PlayerRole.TOP,     region=Region.LCK),
    Player(id=20,  team=DK,   tag="Lucid",       name="Choi Yong-hyeok",            position=PlayerRole.JUNGLE,  region=Region.LCK),
    Player(id=21,  team=DK,   tag="ShowMaker",   name="Heo Su",                     position=PlayerRole.MID,     region=Region.LCK),
    Player(id=22,  team=DK,   tag="Smash",       name="Shin Geum-jae",              position=PlayerRole.ADC,     region=Region.LCK),
    Player(id=23,  team=DK,   tag="Career",      name="Oh Hyeong-seok",             position=PlayerRole.SUPPORT, region=Region.LCK),
    Player(id=24,  team=DK,   tag="cvMax",       name="Kim Dae-ho",                 position=PlayerRole.COACH,   region=Region.LCK),
    # ---------------------------------------------------------------- Anyone's Legend
    Player(id=25,  team=AL,   tag="Breathe",     name="Chen Chen",                  position=PlayerRole.TOP,     region=Region.LPL),
    Player(id=26,  team=AL,   tag="Tarzan",      name="Lee Seung-yong",             position=PlayerRole.JUNGLE,  region=Region.LPL),
    Player(id=27,  team=AL,   tag="Shanks",      name="Cui Xiao-Jun",               position=PlayerRole.MID,     region=Region.LPL),
    Player(id=28,  team=AL,   tag="Hope",        name="Wang Jie",                   position=PlayerRole.ADC,     region=Region.LPL),
    Player(id=29,  team=AL,   tag="Kael",        name="Kim Jin-hong",               position=PlayerRole.SUPPORT, region=Region.LPL),
    Player(id=30,  team=AL,   tag="BigWei",      name="Fu Chien-wei",               position=PlayerRole.COACH,   region=Region.LPL),
    # ---------------------------------------------------------------- Bilibili Gaming
    Player(id=31,  team=BLG,  tag="Bin",         name="Chen Ze-Bin",                position=PlayerRole.TOP,     region=Region.LPL),
    Player(id=32,  team=BLG,  tag="Xun",         name="Peng Li-Xun",                position=PlayerRole.JUNGLE,  region=Region.LPL),
    Player(id=33,  team=BLG,  tag="Knight",      name="Zhuo Ding",                  position=PlayerRole.MID,     region=Region.LPL),
    Player(id=34,  team=BLG,  tag="Viper",       name="Park Do-hyeon",              position=PlayerRole.ADC,     region=Region.LPL),
    Player(id=35,  team=BLG,  tag="ON",          name="Luo Wen-Jun",                position=PlayerRole.SUPPORT, region=Region.LPL),
    Player(id=36,  team=BLG,  tag="Daeny",       name="Yang Dae-in",                position=PlayerRole.COACH,   region=Region.LPL),
    Player(id=37,  team=BLG,  tag="Flandre",     name="Li Xuan-Jun",                position=PlayerRole.TOP,     region=Region.LPL),  # sub
    # ---------------------------------------------------------------- TOP Esports
    Player(id=38,  team=TES,  tag="369",         name="Bai Jia-Hao",                position=PlayerRole.TOP,     region=Region.LPL),  # starts while ZUIAN is visa-blocked
    Player(id=39,  team=TES,  tag="Tian",        name="Gao Tian-Liang",             position=PlayerRole.JUNGLE,  region=Region.LPL),
    Player(id=40,  team=TES,  tag="Creme",       name="Lin Jian",                   position=PlayerRole.MID,     region=Region.LPL),
    Player(id=41,  team=TES,  tag="JackeyLove",  name="Yu Wen-Bo",                  position=PlayerRole.ADC,     region=Region.LPL),
    Player(id=42,  team=TES,  tag="Zhuo",        name="Wang Xu-Zhuo",               position=PlayerRole.SUPPORT, region=Region.LPL),
    Player(id=43,  team=TES,  tag="Poppy",       name="Chang Po-Hao",               position=PlayerRole.COACH,   region=Region.LPL),
    Player(id=44,  team=TES,  tag="ZUIAN",       name="Cheng Zi-Hao",               position=PlayerRole.TOP,     region=Region.LPL),  # sub - US visa denied twice (Oct 6), may rejoin for Swiss
    # ---------------------------------------------------------------- Shanghai Invictus Gaming Meituan
    Player(id=45,  team=IG,   tag="TheShy",      name="Kang Seung-lok",             position=PlayerRole.TOP,     region=Region.LPL),
    Player(id=46,  team=IG,   tag="Wei",         name="Yan Yang-Wei",               position=PlayerRole.JUNGLE,  region=Region.LPL),
    Player(id=47,  team=IG,   tag="Rookie",      name="Song Eui-jin",               position=PlayerRole.MID,     region=Region.LPL),
    Player(id=48,  team=IG,   tag="JiaQi",       name="Zi Jia-Qi",                  position=PlayerRole.ADC,     region=Region.LPL),
    Player(id=49,  team=IG,   tag="Meiko",       name="Tian Ye",                    position=PlayerRole.SUPPORT, region=Region.LPL),
    Player(id=50,  team=IG,   tag="Helper",      name="Kwon Yeong-jae",             position=PlayerRole.COACH,   region=Region.LPL),
    Player(id=51,  team=IG,   tag="Assum",       name="Zou Wei",                    position=PlayerRole.ADC,     region=Region.LPL),  # sub
    # ---------------------------------------------------------------- G2 Esports
    Player(id=52,  team=G2,   tag="BrokenBlade", name="Sergen Çelik",               position=PlayerRole.TOP,     region=Region.LEC),
    Player(id=53,  team=G2,   tag="SkewMond",    name="Rudy Semaan",                position=PlayerRole.JUNGLE,  region=Region.LEC),
    Player(id=54,  team=G2,   tag="Caps",        name="Rasmus Borregaard Winther",  position=PlayerRole.MID,     region=Region.LEC),
    Player(id=55,  team=G2,   tag="Hans Sama",   name="Steven Liv",                 position=PlayerRole.ADC,     region=Region.LEC),
    Player(id=56,  team=G2,   tag="Labrov",      name="Labros Papoutsakis",         position=PlayerRole.SUPPORT, region=Region.LEC),
    Player(id=57,  team=G2,   tag="Perkz",       name="Luka Perković",              position=PlayerRole.COACH,   region=Region.LEC),
    # ---------------------------------------------------------------- Movistar KOI
    Player(id=58,  team=MKOI, tag="Myrwn",       name="Álex Pastor Villarejo",      position=PlayerRole.TOP,     region=Region.LEC),
    Player(id=59,  team=MKOI, tag="Elyoya",      name="Javier Prades Batalla",      position=PlayerRole.JUNGLE,  region=Region.LEC),
    Player(id=60,  team=MKOI, tag="Jojopyun",    name="Joseph Joon Pyun",           position=PlayerRole.MID,     region=Region.LEC),
    Player(id=61,  team=MKOI, tag="Supa",        name="David Martínez García",      position=PlayerRole.ADC,     region=Region.LEC),
    Player(id=62,  team=MKOI, tag="Alvaro",      name="Álvaro Fernández del Amo",   position=PlayerRole.SUPPORT, region=Region.LEC),
    Player(id=63,  team=MKOI, tag="Melzhet",     name="Tomás Campelos",             position=PlayerRole.COACH,   region=Region.LEC),
    Player(id=64,  team=MKOI, tag="NightSlayer", name="Ivan Bilous",                position=PlayerRole.TOP,     region=Region.LEC),  # sub
    # ---------------------------------------------------------------- Karmine Corp
    Player(id=65,  team=KC,   tag="Canna",       name="Kim Chang-dong",             position=PlayerRole.TOP,     region=Region.LEC),
    Player(id=66,  team=KC,   tag="Yike",        name="Martin Sundelin",            position=PlayerRole.JUNGLE,  region=Region.LEC),
    Player(id=67,  team=KC,   tag="kyeahoo",     name="Kang Yea-hoo",               position=PlayerRole.MID,     region=Region.LEC),
    Player(id=68,  team=KC,   tag="Caliste",     name="Caliste Henry-Hennebert",    position=PlayerRole.ADC,     region=Region.LEC),
    Player(id=69,  team=KC,   tag="Busio",       name="Alan Cwalina",               position=PlayerRole.SUPPORT, region=Region.LEC),
    Player(id=70,  team=KC,   tag="Reapered",    name="Bok Han-gyu",                position=PlayerRole.COACH,   region=Region.LEC),
    # ---------------------------------------------------------------- Team Liquid Alienware
    Player(id=71,  team=TL,   tag="Morgan",      name="Park Ru-han",                position=PlayerRole.TOP,     region=Region.LCS),
    Player(id=72,  team=TL,   tag="Josedeodo",   name="Brandon Joel Villegas",      position=PlayerRole.JUNGLE,  region=Region.LCS),
    Player(id=73,  team=TL,   tag="Quid",        name="Lim Hyeon-seung",            position=PlayerRole.MID,     region=Region.LCS),
    Player(id=74,  team=TL,   tag="Yeon",        name="Sean Sung",                  position=PlayerRole.ADC,     region=Region.LCS),
    Player(id=75,  team=TL,   tag="CoreJJ",      name="Jo Yong-in",                 position=PlayerRole.SUPPORT, region=Region.LCS),
    Player(id=76,  team=TL,   tag="Spawn",       name="Jake Tiberi",                position=PlayerRole.COACH,   region=Region.LCS),
    # ---------------------------------------------------------------- LYON
    Player(id=77,  team=LYON, tag="Dhokla",      name="Niship Doshi",               position=PlayerRole.TOP,     region=Region.LCS),
    Player(id=78,  team=LYON, tag="Inspired",    name="Kacper Słoma",               position=PlayerRole.JUNGLE,  region=Region.LCS),
    Player(id=79,  team=LYON, tag="Saint",       name="Kang Sung-in",               position=PlayerRole.MID,     region=Region.LCS),
    Player(id=80,  team=LYON, tag="Berserker",   name="Kim Min-cheol",              position=PlayerRole.ADC,     region=Region.LCS),
    Player(id=81,  team=LYON, tag="Isles",       name="Jonah Rosario",              position=PlayerRole.SUPPORT, region=Region.LCS),
    Player(id=82,  team=LYON, tag="Reignover",   name="Kim Yeu-jin",                position=PlayerRole.COACH,   region=Region.LCS),
    # ---------------------------------------------------------------- Cloud9 Kia
    Player(id=83,  team=C9,   tag="Thanatos",    name="Park Seung-gyu",             position=PlayerRole.TOP,     region=Region.LCS),
    Player(id=84,  team=C9,   tag="Blaber",      name="Robert Huang",               position=PlayerRole.JUNGLE,  region=Region.LCS),
    Player(id=85,  team=C9,   tag="Loki",        name="Lee Sang-min",               position=PlayerRole.MID,     region=Region.LCS),
    Player(id=86,  team=C9,   tag="Tactical",    name="Edward Ra",                  position=PlayerRole.ADC,     region=Region.LCS),
    Player(id=87,  team=C9,   tag="Vulcan",      name="Philippe Laflamme",          position=PlayerRole.SUPPORT, region=Region.LCS),
    Player(id=88,  team=C9,   tag="IWDominate",  name="Christian Rivera",           position=PlayerRole.COACH,   region=Region.LCS),
    Player(id=89,  team=C9,   tag="APA",         name="Eain Stearns",               position=PlayerRole.MID,     region=Region.LCS),  # sub (rotated with Loki in Summer)
    Player(id=90,  team=C9,   tag="Zven",        name="Jesper Svenningsen",         position=PlayerRole.ADC,     region=Region.LCS),  # sub (rotated with Tactical in Summer)
    # ---------------------------------------------------------------- Team Secret Whales
    Player(id=91,  team=TSW,  tag="Pun",         name="Nguyễn Đăng Khoa",           position=PlayerRole.TOP,     region=Region.LCP),
    Player(id=92,  team=TSW,  tag="Hizto",       name="Lê Văn Hoàng Hải",           position=PlayerRole.JUNGLE,  region=Region.LCP),
    Player(id=93,  team=TSW,  tag="Dire",        name="Trần Duy Đức",               position=PlayerRole.MID,     region=Region.LCP),
    Player(id=94,  team=TSW,  tag="Eddie",       name="Hoàng Công Nghĩa",           position=PlayerRole.ADC,     region=Region.LCP),
    Player(id=95,  team=TSW,  tag="Bie",         name="Trần Đức Hiếu",              position=PlayerRole.SUPPORT, region=Region.LCP),
    Player(id=96,  team=TSW,  tag="WarHorse",    name="Chen Ju-Chih",               position=PlayerRole.COACH,   region=Region.LCP),
    # ---------------------------------------------------------------- CTBC Flying Oyster
    Player(id=97,  team=CFO,  tag="Rest",        name="Hsu Shih-chieh",             position=PlayerRole.TOP,     region=Region.LCP),
    Player(id=98,  team=CFO,  tag="Shad0w",      name="Zhao Zhiqiang",              position=PlayerRole.JUNGLE,  region=Region.LCP),
    Player(id=99,  team=CFO,  tag="POUT",        name="Han In-woong",               position=PlayerRole.MID,     region=Region.LCP),
    Player(id=100, team=CFO,  tag="Doggo",       name="Chiu Tzu-chuan",             position=PlayerRole.ADC,     region=Region.LCP),
    Player(id=101, team=CFO,  tag="Kino",        name="Chu Wu Hsin-Jung",           position=PlayerRole.SUPPORT, region=Region.LCP),
    Player(id=102, team=CFO,  tag="Chawy",       name="Wong Xing Lei",              position=PlayerRole.COACH,   region=Region.LCP),
    # ---------------------------------------------------------------- MVK Esports
    Player(id=103, team=MVK,  tag="Kratos",      name="Ngô Đức Khánh",              position=PlayerRole.TOP,     region=Region.LCP),
    Player(id=104, team=MVK,  tag="Gury",        name="Lương Hải Long",             position=PlayerRole.JUNGLE,  region=Region.LCP),
    Player(id=105, team=MVK,  tag="Chika",       name="Võ Lê Nhân",                 position=PlayerRole.MID,     region=Region.LCP),
    Player(id=106, team=MVK,  tag="Harky",       name="Nguyễn Văn Hữu",             position=PlayerRole.ADC,     region=Region.LCP),
    Player(id=107, team=MVK,  tag="SiuLoong",    name="Nguyễn Hoàng Lam",           position=PlayerRole.SUPPORT, region=Region.LCP),
    Player(id=108, team=MVK,  tag="BigKoro",     name="Đặng Ngọc Tài",              position=PlayerRole.COACH,   region=Region.LCP),  # HC per esportsverse roster
    Player(id=109, team=MVK,  tag="SofM",        name="Lê Quang Duy",               position=PlayerRole.COACH,   region=Region.LCP),  # co-owner; HC per Sheep Esports - keep one
    Player(id=110, team=MVK,  tag="SanSan",      name="Lê Quốc Khánh",              position=PlayerRole.JUNGLE,  region=Region.LCP),  # sub
    # ---------------------------------------------------------------- LOS
    Player(id=111, team=LOS,  tag="Zest",        name="Kim Dong-min",               position=PlayerRole.TOP,     region=Region.CBLOL),
    Player(id=112, team=LOS,  tag="Curse",       name="Raí Yamada",                 position=PlayerRole.JUNGLE,  region=Region.CBLOL),
    Player(id=113, team=LOS,  tag="Feisty",      name="Jung Seong-hun",             position=PlayerRole.MID,     region=Region.CBLOL),
    Player(id=114, team=LOS,  tag="Duduhh",      name="Wallyson Silva",             position=PlayerRole.ADC,     region=Region.CBLOL),
    Player(id=115, team=LOS,  tag="Ackerman",    name="Gabriel Aparicio",           position=PlayerRole.SUPPORT, region=Region.CBLOL),
    Player(id=116, team=LOS,  tag="Enatron",     name="Ilias Theodorou",            position=PlayerRole.COACH,   region=Region.CBLOL),
    # ---------------------------------------------------------------- FURIA
    Player(id=117, team=FUR,  tag="Guigo",       name="Guilherme Araújo Ruiz",      position=PlayerRole.TOP,     region=Region.CBLOL),
    Player(id=118, team=FUR,  tag="Tatu",        name="Pedro Seixas",               position=PlayerRole.JUNGLE,  region=Region.CBLOL),
    Player(id=119, team=FUR,  tag="Tutsz",       name="Arthur Peixoto Machado",     position=PlayerRole.MID,     region=Region.CBLOL),
    Player(id=120, team=FUR,  tag="Ayu",         name="Andrey Saraiva",             position=PlayerRole.ADC,     region=Region.CBLOL),
    Player(id=121, team=FUR,  tag="JoJo",        name="Gabriel Dzelme de Oliveira", position=PlayerRole.SUPPORT, region=Region.CBLOL),
    Player(id=122, team=FUR,  tag="furyz",       name="Erick Susin Pereira",        position=PlayerRole.COACH,   region=Region.CBLOL),
    Player(id=123, team=FUR,  tag="Shini",       name="Diogo Rogê",                 position=PlayerRole.JUNGLE,  region=Region.CBLOL),  # sub
]

