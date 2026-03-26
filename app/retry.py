# shared retry engine — used by ALL handlers
from __future__ import annotations

import asyncio
import random
from typing import Any, Awaitable, Callable

from app.config import HandlerConfig
from app.models import AttemptRecord

RETRYABLE_EXCEPTIONS = (TimeoutError, ConnectionError, ConnectionRefusedError)


async def async_retry(
    coro_factory: Callable[..., Awaitable[Any]],
    config: HandlerConfig,
    on_attempt: Callable[[AttemptRecord], None],
) -> Any:
    last_exc: Exception | None = None

    for attempt in range(config.max_retries + 1):
        if attempt > 0:
            delay = min(
                config.backoff_base * 2**attempt + random.uniform(0, config.jitter_max),
                config.backoff_cap,
            )
            await asyncio.sleep(delay)
        else:
            delay = 0.0

        try:
            result = await coro_factory()
            on_attempt(AttemptRecord(attempt_number=attempt, applied_delay=delay))
            return result
        except RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
            on_attempt(
                AttemptRecord(
                    attempt_number=attempt, applied_delay=delay, error=str(exc)
                )
            )
        except Exception as exc:
            on_attempt(
                AttemptRecord(
                    attempt_number=attempt, applied_delay=delay, error=str(exc)
                )
            )
            raise

    raise last_exc  # type: ignore[misc]
