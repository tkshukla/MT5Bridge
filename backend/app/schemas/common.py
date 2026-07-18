from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    kotak_feed: str
    db: str
    redis: str
    version: str = "0.1.0"


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
