from fastapi import FastAPI

from routers import auth, draft, leagues, trades

app = FastAPI(title="LoL Fantasy API", version="0.1.0", root_path="/api")

app.include_router(auth.router)
app.include_router(leagues.router)
app.include_router(draft.router)
app.include_router(trades.router)


@app.get("/health", tags=["meta"])
def health():
    return {"ok": True}
