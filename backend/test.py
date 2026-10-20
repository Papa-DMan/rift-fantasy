from app.db import DBManager, seed, DBConfig

conf = DBConfig(
    host="localhost",
    port=5432,
    database="lolesports_fantasy",
    user="postgres",
    password="qwerpoiu"
)

dbm = DBManager(conf)

# dbm.create_all()
session = dbm.get_session()
seed(session)