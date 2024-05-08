"""The air-Q integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from aioairq import AirQ

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, MANUFACTURER, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AirQCoordinator(DataUpdateCoordinator):
    """Coordinator is responsible for querying the device at a specified route."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialise a custom coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        session = async_get_clientsession(hass)
        self.airq = AirQ(
            entry.data[CONF_IP_ADDRESS], entry.data[CONF_PASSWORD], session
        )
        self.device_id = entry.unique_id
        assert self.device_id is not None
        self.device_info = DeviceInfo(
            manufacturer=MANUFACTURER,
            identifiers={(DOMAIN, self.device_id)},
        )

    async def _async_update_data(self) -> dict:
        """Fetch the data from the device."""
        if "name" not in self.device_info:
            info = await self.airq.fetch_device_info()
            self.device_info.update(
                DeviceInfo(
                    name=info["name"],
                    model=info["model"],
                    sw_version=info["sw_version"],
                    hw_version=info["hw_version"],
                )
            )
        return await self.airq.get_latest_data()  # type: ignore[no-any-return]
