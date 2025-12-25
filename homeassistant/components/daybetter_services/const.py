"""Constants for DayBetter Services integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

DOMAIN = "daybetter_services"

CONF_USER_CODE = "user_code"
CONF_TOKEN = "token"

if TYPE_CHECKING:
    from daybetter_python import DayBetterClient

    from .coordinator import DayBetterCoordinator


@dataclass(slots=True)
class DayBetterRuntimeData:
    """Runtime data stored on the config entry."""

    coordinator: DayBetterCoordinator
    client: DayBetterClient


DayBetterConfigEntry = ConfigEntry[DayBetterRuntimeData]
