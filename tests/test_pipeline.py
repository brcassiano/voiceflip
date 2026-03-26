# tests for pipeline orchestration
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.models import HandlerResult, RequestStatus
from app.pipeline import run_pipeline
from app.store import InMemoryStore


@pytest.fixture
def store():
    return InMemoryStore()


@pytest.mark.asyncio
async def test_ok_scenario(store):
    """Both handlers succeed → completed, not degraded."""
    record = store.create({"scenario": "ok"})
    await run_pipeline(record.id, record.payload, store)

    result = store.get(record.id)
    assert result.status == RequestStatus.COMPLETED
    assert result.degraded is False
    assert result.primary_result.success is True
    assert result.optional_result.success is True


@pytest.mark.asyncio
async def test_hard_fail_primary(store):
    """Primary hard_fail → status=failed."""
    record = store.create({"scenario": "hard_fail"})
    await run_pipeline(record.id, record.payload, store)

    result = store.get(record.id)
    assert result.status == RequestStatus.FAILED
    assert result.primary_result.success is False
    assert "Hard failure" in result.primary_result.error


@pytest.mark.asyncio
async def test_transient_fail_then_ok(store):
    """Transient failures recover after retries → completed."""
    record = store.create({"scenario": "transient_fail_then_ok", "fail_times": 1})
    await run_pipeline(record.id, record.payload, store)

    result = store.get(record.id)
    assert result.status == RequestStatus.COMPLETED
    assert result.degraded is False
    assert result.primary_result.success is True
    assert result.optional_result.success is True


@pytest.mark.asyncio
async def test_timeout_scenario(store):
    """Both handlers timeout → primary fails → status=failed."""
    record = store.create({"scenario": "timeout"})
    await run_pipeline(record.id, record.payload, store)

    result = store.get(record.id)
    assert result.status == RequestStatus.FAILED


@pytest.mark.asyncio
async def test_degraded_mode(store):
    """Primary succeeds but optional fails → completed + degraded."""
    record = store.create({"scenario": "ok"})

    failed_optional = HandlerResult(
        success=False, latency_ms=100.0, error="optional handler timed out"
    )

    original_run_pipeline = run_pipeline.__wrapped__ if hasattr(run_pipeline, '__wrapped__') else None

    with patch("app.pipeline.run_optional_handler", new_callable=AsyncMock) as mock_opt:
        mock_opt.return_value = failed_optional
        await run_pipeline(record.id, record.payload, store)

    result = store.get(record.id)
    assert result.status == RequestStatus.COMPLETED
    assert result.degraded is True
    assert result.degradation_reason == "optional handler timed out"
    assert result.primary_result.success is True


@pytest.mark.asyncio
async def test_metrics_updated(store):
    """Metrics counters are updated after pipeline runs."""
    record = store.create({"scenario": "ok"})
    await run_pipeline(record.id, record.payload, store)

    assert store.total_processed == 1
    assert store.primary_success == 1
    assert store.optional_success == 1
    assert len(store.latency_samples["primary"]) == 1
    assert len(store.latency_samples["optional"]) == 1
