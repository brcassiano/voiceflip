# ALL configurable constants and parameters
from dataclasses import dataclass


@dataclass
class HandlerConfig:
    timeout_seconds: float
    max_retries: int
    backoff_base: float
    backoff_cap: float
    jitter_max: float


DEFAULT_PRIMARY_CONFIG = HandlerConfig(
    timeout_seconds=10.0,
    max_retries=3,
    backoff_base=0.5,
    backoff_cap=10.0,
    jitter_max=0.3,
)

DEFAULT_OPTIONAL_CONFIG = HandlerConfig(
    timeout_seconds=3.0,
    max_retries=2,
    backoff_base=0.3,
    backoff_cap=5.0,
    jitter_max=0.2,
)

SIMULATED_LATENCY = 0.05
