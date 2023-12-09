"""Constants used by Tessie integration."""
from __future__ import annotations

from enum import StrEnum

DOMAIN = "tessie"

MODELS = {
    "model3": "Model 3",
    "modelx": "Model X",
    "modely": "Model Y",
    "models": "Model S",
}


class TessieStatus(StrEnum):
    """Tessie status."""

    ASLEEP = "asleep"
    ONLINE = "online"
    OFFLINE = "offline"
