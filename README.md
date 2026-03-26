# VoiceFlip Resilient Processing Pipeline

A FastAPI-based processing pipeline that demonstrates resilient async request handling with retry/backoff logic, graceful degradation, and real-time observability.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running the Server

```bash
uvicorn app.main:app --reload
```

The API runs on `http://localhost:8000`. You can also access the interactive Swagger UI at `http://localhost:8000/docs`.

## API Endpoints

### POST /requests

Submit a processing request with a scenario.

```bash
# Happy path — both handlers succeed
curl -s -X POST http://localhost:8000/requests -H "Content-Type: application/json" -d '{"payload": {"scenario": "ok"}}'

# Transient failures that recover after retries (both handlers recover)
curl -s -X POST http://localhost:8000/requests -H "Content-Type: application/json" -d '{"payload": {"scenario": "transient_fail_then_ok", "fail_times": 2}}'

# Degraded mode — primary recovers but optional exhausts retries
curl -s -X POST http://localhost:8000/requests -H "Content-Type: application/json" -d '{"payload": {"scenario": "transient_fail_then_ok", "fail_times": 3}}'

# Timeout — both handlers exceed their deadline
curl -s -X POST http://localhost:8000/requests -H "Content-Type: application/json" -d '{"payload": {"scenario": "timeout"}}'

# Hard failure — non-retryable error, no retry attempted
curl -s -X POST http://localhost:8000/requests -H "Content-Type: application/json" -d '{"payload": {"scenario": "hard_fail"}}'
```

### GET /requests/{request_id}

Check the status and results of a request. Returns the full request record including status, degraded flag, handler results, and retry history per handler.

```bash
curl -s http://localhost:8000/requests/<request_id> | python3 -m json.tool
```

### GET /health

View processing metrics: success/failure counters and average latency per handler.

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

## Scenarios Explained

| Scenario | Behavior | Expected Status |
|----------|----------|-----------------|
| `ok` | Both handlers succeed immediately | `completed`, `degraded: false` |
| `transient_fail_then_ok` (fail_times=2) | Both handlers fail transiently then recover via retries | `completed`, `degraded: false` |
| `transient_fail_then_ok` (fail_times=3) | Primary recovers (has 3 retries), optional exhausts retries (has 2) | `completed`, `degraded: true` |
| `timeout` | Both handlers raise TimeoutError (retryable, but keeps failing) | `failed` |
| `hard_fail` | Both handlers raise ValueError (non-retryable, no retry attempted) | `failed` |

## Running Tests

```bash
python -m pytest tests/ -v
```

16 tests covering retry logic, pipeline orchestration, and E2E API flows.

## Architecture

```
app/
  models.py      — Pydantic schemas (RequestRecord, HandlerResult, AttemptRecord)
  config.py      — All configurable values (timeouts, retries, backoff params)
  store.py       — In-memory store with thread-safe CRUD and metrics
  retry.py       — Shared retry engine with exponential backoff + jitter
  handlers.py    — Primary and optional handlers with 4 deterministic scenarios
  pipeline.py    — Orchestrator: asyncio.gather for parallel handler execution
  api/routes.py  — 3 FastAPI endpoints
  main.py        — FastAPI app entry point (no business logic)
```

The pipeline runs two handlers in parallel using `asyncio.gather`:
- **Primary handler** (timeout: 10s, max retries: 3) — must succeed for the request to complete
- **Optional handler** (timeout: 3s, max retries: 2) — can fail gracefully (degraded mode)

Both handlers delegate retry logic to a single shared `async_retry()` function with exponential backoff and jitter.

## Demo

[Loom video walkthrough](https://www.loom.com/share/PLACEHOLDER)
