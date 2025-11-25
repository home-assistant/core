"""Anglian Water data coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

from pyanglianwater import AnglianWater
from pyanglianwater.exceptions import ExpiredAccessTokenError, UnknownEndpointError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

type AnglianWaterConfigEntry = ConfigEntry[AnglianWaterUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(minutes=60)


class AnglianWaterUpdateCoordinator(DataUpdateCoordinator[None]):
    """Anglian Water data update coordinator."""

    config_entry: AnglianWaterConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: AnglianWater,
        config_entry: AnglianWaterConfigEntry,
    ) -> None:
        """Initialize update coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self.api = api

    async def _async_update_data(self) -> None:
        """Update data from Anglian Water's API."""
        try:
            return await self.api.update()
        except (ExpiredAccessTokenError, UnknownEndpointError) as err:
            raise UpdateFailed from err
