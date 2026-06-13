"""FastAPI backend — handles the dashboard API and runs the email polling on a schedule."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import storage
from .poller import poll_once

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)
log = logging.getLogger("app")

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "120"))
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("starting up — email_source=%s, polling every %ss",
             os.getenv("EMAIL_SOURCE", "mock"), POLL_INTERVAL)
    storage.init_db()
    log.info("running initial poll on startup...")
    poll_once()
    scheduler.add_job(poll_once, "interval", seconds=POLL_INTERVAL, id="poll")
    scheduler.start()
    log.info("scheduler is running, will poll every %ss", POLL_INTERVAL)
    yield
    log.info("shutting down...")
    scheduler.shutdown(wait=False)


app = FastAPI(title="AI Email Reading Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/notifications")
def notifications():
    notes = storage.get_notifications()
    return {
        "stats": storage.stats(),
        "poll_interval_seconds": POLL_INTERVAL,
        "notifications": [n.model_dump(by_alias=True, mode="json") for n in notes],
    }


@app.post("/api/poll")
def manual_poll():
    log.info("manual poll triggered")
    return poll_once()


@app.get("/api/health")
def health():
    return {"status": "ok"}


# serve the frontend if it's been built
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")
