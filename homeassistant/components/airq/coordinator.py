"""The air-Q integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from aioairq.core import AirQ, identify_warming_up_sensors

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

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        clip_negative: bool = True,
        return_average: bool = True,
    ) -> None:
        """Initialise a custom coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
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
        self.clip_negative = clip_negative
        self.return_average = return_average

    async def _async_update_data(self) -> dict:
        """Fetch the data from the device."""
        if "name" not in self.device_info:
            _LOGGER.debug(
                "'name' not found in AirQCoordinator.device_info, fetching from the device"
            )
            info = await self.airq.fetch_device_info()
            self.device_info.update(
                DeviceInfo(
                    name=info["name"],
                    model=info["model"],
                    sw_version=info["sw_version"],
                    hw_version=info["hw_version"],
                )
            )
            _LOGGER.debug(
                "Updated AirQCoordinator.device_info for 'name' %s",
                self.device_info.get("name"),
            )
        data: dict = await self.airq.get_latest_data(
            return_average=self.return_average,
            clip_negative_values=self.clip_negative,
        )
        if warming_up_sensors := identify_warming_up_sensors(data):
            _LOGGER.debug(
                "Following sensors are still warming up: %s", warming_up_sensors
            )
        return data
