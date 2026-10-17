"""Data update coordinator for the EcoTracker integration."""

from datetime import timedelta
import logging
from typing import override

from ecotracker import EcoTracker
from ecotracker.data import EcoTrackerData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_FAST_POLLING,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    FAST_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type EcoTrackerConfigEntry = ConfigEntry[EcoTrackerDataUpdateCoordinator]


class EcoTrackerDataUpdateCoordinator(DataUpdateCoordinator[EcoTrackerData]):
    """Class to manage fetching EcoTracker data."""

    config_entry: EcoTrackerConfigEntry
    client: EcoTracker

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        config_entry: EcoTrackerConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            # Entries created before the option existed have no options.
            update_interval=timedelta(
                seconds=FAST_UPDATE_INTERVAL
                if config_entry.options.get(CONF_FAST_POLLING, False)
                else DEFAULT_UPDATE_INTERVAL
            ),
        )
        self.client = EcoTracker(host, port=80, session=async_get_clientsession(hass))
        self.host = host

    @override
    async def _async_update_data(self) -> EcoTrackerData:
        """Fetch data from the EcoTracker device."""
        if await self.client.async_update():
            return self.client.get_data()
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="update_failed",
        )
