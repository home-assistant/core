"""Constants used by Teslemetry integration."""
from __future__ import annotations

from enum import StrEnum

DOMAIN = "teslemetry"

MODELS = {
    "model3": "Model 3",
    "modelx": "Model X",
    "modely": "Model Y",
    "models": "Model S",
}


class TeslemetryClimateSide(StrEnum):
    """Teslemetry Climate Keeper Modes."""

    DRIVER = "driver"
    PASSENGER = "passenger"
