"""Zeversolar coordinator."""

from datetime import timedelta
import logging

import zeversolar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type ZeversolarConfigEntry = ConfigEntry[ZeversolarCoordinator]


class ZeversolarCoordinator(DataUpdateCoordinator[zeversolar.ZeverSolarData]):
    """Data update coordinator."""

    config_entry: ZeversolarConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ZeversolarConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )
        self._client = zeversolar.ZeverSolarClient(host=entry.data[CONF_HOST])

    async def _async_update_data(self) -> zeversolar.ZeverSolarData:
        """Fetch the latest data from the source."""
        try:
            return await self.hass.async_add_executor_job(self._client.get_data)
        except zeversolar.ZeverSolarError as err:
            raise UpdateFailed(err) from err
