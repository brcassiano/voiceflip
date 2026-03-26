# 3 FastAPI route definitions
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.pipeline import run_pipeline
from app.store import InMemoryStore

router = APIRouter()


def _get_store():
    from app.main import get_store

    return get_store()


@router.post("/requests")
async def create_request(
    body: dict,
    background_tasks: BackgroundTasks,
    store: InMemoryStore = Depends(_get_store),
):
    record = store.create(body.get("payload", {}))
    background_tasks.add_task(run_pipeline, record.id, record.payload, store)
    return {"request_id": str(record.id), "status": "pending"}


@router.get("/requests/{request_id}")
async def get_request(
    request_id: UUID,
    store: InMemoryStore = Depends(_get_store),
):
    record = store.get(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return record


@router.get("/health")
async def health(store: InMemoryStore = Depends(_get_store)):
    snapshot = store.health_snapshot()
    return {
        "total_processed": snapshot["total_processed"],
        "primary": {
            "success": snapshot["primary_success"],
            "failure": snapshot["primary_failure"],
            "avg_latency_ms": snapshot["avg_latency_primary"],
        },
        "optional": {
            "success": snapshot["optional_success"],
            "failure": snapshot["optional_failure"],
            "avg_latency_ms": snapshot["avg_latency_optional"],
        },
    }
