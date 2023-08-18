"""Amber Electric Coordinator."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from blinkpy.blinkpy import Blink

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BlinkUpdateCoordinator(DataUpdateCoordinator):
    """BlinkUpdateCoordinator - In charge of downloading the data for a site, which all the sensors read."""

    def __init__(self, hass: HomeAssistant, api: Blink) -> None:
        """Initialise the data service."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Async update wrapper."""
        _LOGGER.debug(
            "Initiating a blink.refresh() from BlinkSyncModule() (%s)",
            self.api,
        )
        try:
            return await self.api.refresh(force=True)
        except asyncio.TimeoutError as err:
            raise UpdateFailed("Update Failed") from err
