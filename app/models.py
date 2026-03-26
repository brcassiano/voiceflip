# SINGLE source of truth for all schemas/enums
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RequestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AttemptRecord(BaseModel):
    attempt_number: int
    applied_delay: float
    error: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HandlerResult(BaseModel):
    success: bool
    latency_ms: float
    result: Any | None = None
    error: str | None = None
    attempts: list[AttemptRecord] = []


class RequestRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    payload: dict
    status: RequestStatus = RequestStatus.PENDING
    degraded: bool = False
    degradation_reason: str | None = None
    primary_result: HandlerResult | None = None
    optional_result: HandlerResult | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None
