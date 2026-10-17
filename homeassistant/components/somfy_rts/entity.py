"""Shared data types for the Somfy RTS integration."""

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.storage import Store


class SomfyRTSData:
    """Shared runtime data for a Somfy RTS config entry."""

    def __init__(self, *, store: Store, rolling_code: int) -> None:
        """Initialize runtime data."""
        self.store = store
        self.rolling_code = rolling_code
        self.lock = asyncio.Lock()


type SomfyRTSConfigEntry = ConfigEntry[SomfyRTSData]
