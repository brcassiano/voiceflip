# tests for retry engine
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import HandlerConfig
from app.retry import async_retry


CFG = HandlerConfig(
    timeout_seconds=5.0,
    max_retries=3,
    backoff_base=0.5,
    backoff_cap=10.0,
    jitter_max=0.3,
)


@pytest.mark.asyncio
async def test_delay_formula():
    """delay = min(base * 2^attempt + jitter, cap)"""
    call_count = 0

    async def _coro():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise TimeoutError("boom")
        return "ok"

    recorded = []

    with patch("app.retry.random.uniform", return_value=0.1) as mock_uniform, \
         patch("app.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await async_retry(_coro, CFG, lambda rec: recorded.append(rec))

    assert result == "ok"
    assert call_count == 3

    # attempt 0: no sleep
    # attempt 1: min(0.5 * 2^1 + 0.1, 10.0) = 1.1
    # attempt 2: min(0.5 * 2^2 + 0.1, 10.0) = 2.1
    assert mock_sleep.call_count == 2
    assert mock_sleep.call_args_list[0][0][0] == pytest.approx(1.1)
    assert mock_sleep.call_args_list[1][0][0] == pytest.approx(2.1)


@pytest.mark.asyncio
async def test_jitter_bounds():
    """random.uniform is called with (0, config.jitter_max)"""
    call_count = 0

    async def _coro():
        nonlocal call_count
        call_count += 1
        if call_count <= 1:
            raise ConnectionError("fail")
        return "ok"

    with patch("app.retry.random.uniform", return_value=0.1) as mock_uniform, \
         patch("app.retry.asyncio.sleep", new_callable=AsyncMock):
        await async_retry(_coro, CFG, lambda rec: None)

    mock_uniform.assert_called_with(0, CFG.jitter_max)


@pytest.mark.asyncio
async def test_non_retryable_error_propagates_immediately():
    """ValueError (non-retryable) should propagate without retry."""
    call_count = 0

    async def _coro():
        nonlocal call_count
        call_count += 1
        raise ValueError("hard fail")

    recorded = []
    with pytest.raises(ValueError, match="hard fail"):
        await async_retry(_coro, CFG, lambda rec: recorded.append(rec))

    assert call_count == 1
    assert len(recorded) == 1
    assert recorded[0].error == "hard fail"


@pytest.mark.asyncio
async def test_retryable_exceptions_are_retried():
    """TimeoutError/ConnectionError should be retried up to max_retries."""
    call_count = 0

    async def _coro():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise TimeoutError("timeout")
        return "done"

    with patch("app.retry.asyncio.sleep", new_callable=AsyncMock):
        result = await async_retry(_coro, CFG, lambda rec: None)

    assert result == "done"
    assert call_count == 3


@pytest.mark.asyncio
async def test_exhausted_retries_reraise():
    """After max_retries+1 attempts, the last exception is re-raised."""
    call_count = 0

    async def _coro():
        nonlocal call_count
        call_count += 1
        raise ConnectionError(f"fail #{call_count}")

    recorded = []
    with patch("app.retry.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(ConnectionError, match="fail #4"):
            await async_retry(_coro, CFG, lambda rec: recorded.append(rec))

    assert call_count == CFG.max_retries + 1
    assert len(recorded) == CFG.max_retries + 1
