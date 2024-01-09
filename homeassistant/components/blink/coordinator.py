"""Blink Coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from blinkpy.blinkpy import Blink

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = 300


class BlinkUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """BlinkUpdateCoordinator - In charge of downloading the data for a site."""

    def __init__(self, hass: HomeAssistant, api: Blink) -> None:
        """Initialize the data service."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Async update wrapper."""
        return await self.api.refresh(force=True)
