"""IoTaWatt DataUpdateCoordinator."""
from __future__ import annotations

from datetime import timedelta
import logging

from iotawattpy.iotawatt import Iotawatt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import httpx_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class IotawattUpdater(DataUpdateCoordinator):
    """Class to manage fetching update data from the IoTaWatt Energy Device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize IotaWattUpdater object."""
        self.api = Iotawatt(
            entry.title,
            entry.data[CONF_HOST],
            httpx_client.get_async_client(hass),
            entry.data.get(CONF_USERNAME),
            entry.data.get(CONF_PASSWORD),
        )

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=entry.title,
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self):
        """Fetch sensors from IoTaWatt device."""
        await self.api.update()
        return self.api.getSensors()
