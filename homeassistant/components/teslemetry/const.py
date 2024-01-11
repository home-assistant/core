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


class TeslemetryClimateKeeper(StrEnum):
    """Teslemetry Climate Keeper Modes."""

    OFF = "off"
    ON = "on"
    DOG = "dog"
    CAMP = "camp"
