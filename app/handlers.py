# Deterministic scenario handlers — delegate ALL retry logic to async_retry
from __future__ import annotations

import asyncio
import time
from typing import Callable
from uuid import UUID

from app.config import SIMULATED_LATENCY, HandlerConfig
from app.models import AttemptRecord, HandlerResult
from app.retry import async_retry

_attempt_counters: dict[tuple[UUID, str], int] = {}


async def run_primary_handler(
    request_id: UUID,
    payload: dict,
    config: HandlerConfig,
    on_attempt_cb: Callable[[AttemptRecord], None],
) -> HandlerResult:
    return await _run_handler("primary", request_id, payload, config, on_attempt_cb)


async def run_optional_handler(
    request_id: UUID,
    payload: dict,
    config: HandlerConfig,
    on_attempt_cb: Callable[[AttemptRecord], None],
) -> HandlerResult:
    return await _run_handler("optional", request_id, payload, config, on_attempt_cb)


async def _run_handler(
    handler_name: str,
    request_id: UUID,
    payload: dict,
    config: HandlerConfig,
    on_attempt_cb: Callable[[AttemptRecord], None],
) -> HandlerResult:
    attempts: list[AttemptRecord] = []
    key = (request_id, handler_name)
    _attempt_counters[key] = 0
    scenario = payload.get("scenario", "ok")

    def _capture_attempt(record: AttemptRecord) -> None:
        attempts.append(record)
        on_attempt_cb(record)

    async def _execute():
        _attempt_counters[key] += 1
        current = _attempt_counters[key]

        if scenario == "ok":
            await asyncio.sleep(SIMULATED_LATENCY)
            return {"status": "ok", "handler": handler_name}

        if scenario == "timeout":
            raise asyncio.TimeoutError(f"Timeout in {handler_name} handler")

        if scenario == "transient_fail_then_ok":
            fail_times = payload.get("fail_times", 2)
            if current <= fail_times:
                raise ConnectionError(
                    f"Transient failure {current}/{fail_times} in {handler_name}"
                )
            await asyncio.sleep(SIMULATED_LATENCY)
            return {"status": "ok", "handler": handler_name, "recovered": True}

        if scenario == "hard_fail":
            raise ValueError(
                f"Hard failure: non-retryable error for {request_id} in {handler_name}"
            )

        raise ValueError(f"Unknown scenario: {scenario}")

    t0 = time.perf_counter()
    try:
        result = await async_retry(_execute, config, _capture_attempt)
        latency_ms = (time.perf_counter() - t0) * 1000
        return HandlerResult(
            success=True, latency_ms=latency_ms, result=result, attempts=attempts
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - t0) * 1000
        return HandlerResult(
            success=False, latency_ms=latency_ms, error=str(exc), attempts=attempts
        )
