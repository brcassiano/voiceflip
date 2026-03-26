# asyncio orchestrator for parallel handler execution
from __future__ import annotations

import asyncio
import time
from datetime import datetime
from uuid import UUID

from app.config import DEFAULT_OPTIONAL_CONFIG, DEFAULT_PRIMARY_CONFIG
from app.handlers import run_optional_handler, run_primary_handler
from app.models import AttemptRecord, HandlerResult, RequestStatus
from app.store import InMemoryStore


async def run_pipeline(
    request_id: UUID, payload: dict, store: InMemoryStore
) -> None:
    store.update(request_id, status=RequestStatus.RUNNING, started_at=datetime.utcnow())

    primary_attempts: list[AttemptRecord] = []
    optional_attempts: list[AttemptRecord] = []

    async def _run_primary() -> HandlerResult:
        return await asyncio.wait_for(
            run_primary_handler(
                request_id,
                payload,
                DEFAULT_PRIMARY_CONFIG,
                lambda rec: primary_attempts.append(rec),
            ),
            timeout=DEFAULT_PRIMARY_CONFIG.timeout_seconds,
        )

    async def _run_optional() -> HandlerResult:
        return await asyncio.wait_for(
            run_optional_handler(
                request_id,
                payload,
                DEFAULT_OPTIONAL_CONFIG,
                lambda rec: optional_attempts.append(rec),
            ),
            timeout=DEFAULT_OPTIONAL_CONFIG.timeout_seconds,
        )

    t0 = time.perf_counter()
    results = await asyncio.gather(
        _run_primary(), _run_optional(), return_exceptions=True
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    primary_raw, optional_raw = results

    # Build HandlerResult for primary
    if isinstance(primary_raw, Exception):
        error_msg = (
            f"TimeoutError: handler exceeded {DEFAULT_PRIMARY_CONFIG.timeout_seconds} seconds"
            if isinstance(primary_raw, asyncio.TimeoutError)
            else str(primary_raw)
        )
        primary_result = HandlerResult(
            success=False, latency_ms=elapsed_ms, error=error_msg, attempts=primary_attempts
        )
    else:
        primary_result = primary_raw

    # Build HandlerResult for optional
    if isinstance(optional_raw, Exception):
        error_msg = (
            f"TimeoutError: handler exceeded {DEFAULT_OPTIONAL_CONFIG.timeout_seconds} seconds"
            if isinstance(optional_raw, asyncio.TimeoutError)
            else str(optional_raw)
        )
        optional_result = HandlerResult(
            success=False, latency_ms=elapsed_ms, error=error_msg, attempts=optional_attempts
        )
    else:
        optional_result = optional_raw

    # Determine final status
    if not primary_result.success:
        status = RequestStatus.FAILED
        degraded = False
        degradation_reason = None
    elif not optional_result.success:
        status = RequestStatus.COMPLETED
        degraded = True
        degradation_reason = optional_result.error
    else:
        status = RequestStatus.COMPLETED
        degraded = False
        degradation_reason = None

    store.update(
        request_id,
        status=status,
        degraded=degraded,
        degradation_reason=degradation_reason,
        primary_result=primary_result,
        optional_result=optional_result,
        finished_at=datetime.utcnow(),
    )

    # Update metrics
    with store._lock:
        store.total_processed += 1
        if primary_result.success:
            store.primary_success += 1
        else:
            store.primary_failure += 1
        if optional_result.success:
            store.optional_success += 1
        else:
            store.optional_failure += 1
        store.latency_samples["primary"].append(primary_result.latency_ms)
        store.latency_samples["optional"].append(optional_result.latency_ms)
