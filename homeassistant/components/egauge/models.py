"""Data models for the eGauge integration."""

from __future__ import annotations

from dataclasses import dataclass

from egauge_async.json.models import RegisterInfo


@dataclass
class EgaugeData:
    """Data from eGauge device."""

    measurements: dict[str, float]  # Instantaneous values (W, V, A, etc.)
    counters: dict[str, float]  # Cumulative values (Ws)
    register_info: dict[str, RegisterInfo]  # Metadata for all registers
