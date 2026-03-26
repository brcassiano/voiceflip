# in-memory store + metrics counters
from __future__ import annotations

import threading
from uuid import UUID

from app.models import RequestRecord, RequestStatus


class InMemoryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[UUID, RequestRecord] = {}

        # metrics counters
        self.total_processed: int = 0
        self.primary_success: int = 0
        self.primary_failure: int = 0
        self.optional_success: int = 0
        self.optional_failure: int = 0

        # latency samples
        self.latency_samples: dict[str, list[float]] = {
            "primary": [],
            "optional": [],
        }

    def create(self, payload: dict) -> RequestRecord:
        record = RequestRecord(payload=payload)
        with self._lock:
            self._records[record.id] = record
        return record

    def get(self, id: UUID) -> RequestRecord | None:
        with self._lock:
            return self._records.get(id)

    def update(self, id: UUID, **fields) -> RequestRecord:
        with self._lock:
            record = self._records[id]
            updated = record.model_copy(update=fields)
            self._records[id] = updated
            return updated

    def list_all(self) -> list[RequestRecord]:
        with self._lock:
            return list(self._records.values())

    def health_snapshot(self) -> dict:
        with self._lock:
            primary_samples = self.latency_samples["primary"]
            optional_samples = self.latency_samples["optional"]
            return {
                "total_processed": self.total_processed,
                "primary_success": self.primary_success,
                "primary_failure": self.primary_failure,
                "optional_success": self.optional_success,
                "optional_failure": self.optional_failure,
                "avg_latency_primary": (
                    sum(primary_samples) / len(primary_samples)
                    if primary_samples
                    else 0.0
                ),
                "avg_latency_optional": (
                    sum(optional_samples) / len(optional_samples)
                    if optional_samples
                    else 0.0
                ),
            }
