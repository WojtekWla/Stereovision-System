import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator


LOG_FILE = "./logging_server/ingest.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 1 MiB
LOG_BACKUP_COUNT = 1
MAX_MESSAGE_CHARS = 10000

logger = logging.getLogger(LOG_FILE)
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = RotatingFileHandler(
        LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
    )
    formatter = logging.Formatter(
        fmt="%(asctime)s\t%(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

app = FastAPI(title="Logging Server", version="1.0.0")


class LogItem(BaseModel):
    message: str = Field(..., description="The message to log")
    level: Optional[str] = Field("INFO")
    source: Optional[str] = Field(None)
    timestamp: Optional[str] = Field(None)

@app.post("/log")
async def ingest_log(
    request: Request
) -> Response:
    payload = await request.json()
    item = LogItem(**payload)

    log_method = {
        "DEBUG": logger.debug,
        "INFO": logger.info,
        "WARNING": logger.warning,
        "ERROR": logger.error,
        "CRITICAL": logger.critical,
    }[item.level or "INFO"]

    log_method(item.message)

    return JSONResponse({"status": "logged"})

@app.get_frame("/")
async def root():
    return JSONResponse({"status": "ok"})