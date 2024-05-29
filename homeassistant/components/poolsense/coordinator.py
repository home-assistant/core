"""DataUpdateCoordinator for poolsense integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from poolsense import PoolSense
from poolsense.exceptions import PoolSenseError

from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import PoolSenseConfigEntry

_LOGGER = logging.getLogger(__name__)


class PoolSenseDataUpdateCoordinator(DataUpdateCoordinator[dict[str, StateType]]):
    """Define an object to hold PoolSense data."""

    config_entry: PoolSenseConfigEntry

    def __init__(self, hass: HomeAssistant, poolsense: PoolSense) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(hours=1))
        self.poolsense = poolsense
        self.email = self.config_entry.data[CONF_EMAIL]

    async def _async_update_data(self) -> dict[str, StateType]:
        """Update data via library."""
        async with asyncio.timeout(10):
            try:
                return await self.poolsense.get_poolsense_data()
            except PoolSenseError as error:
                _LOGGER.error("PoolSense query did not complete")
                raise UpdateFailed(error) from error
