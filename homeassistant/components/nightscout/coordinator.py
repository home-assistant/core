"""Data update coordinator for the Nightscout integration."""

from datetime import timedelta
import logging
from typing import override

from aiohttp import ClientError
from py_nightscout import Api as NightscoutAPI
from py_nightscout.models import SGV

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)

type NightscoutConfigEntry = ConfigEntry[NightscoutGlucoseCoordinator]


class NightscoutGlucoseCoordinator(DataUpdateCoordinator[SGV | None]):
    """Fetch the latest glucose reading from Nightscout."""

    config_entry: NightscoutConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: NightscoutConfigEntry,
        api: NightscoutAPI,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api

    @override
    async def _async_update_data(self) -> SGV | None:
        """Fetch the latest glucose reading, or None if there is none."""
        try:
            values = await self.api.get_sgvs()
        except (ClientError, TimeoutError, OSError) as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(error)},
            ) from error
        return values[0] if values else None
