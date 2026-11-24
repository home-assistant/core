"""The Airzone integration."""

from asyncio import Lock, timeout
from datetime import timedelta
import logging
from typing import Any, override

from aioairzone.exceptions import AirzoneError
from aioairzone.localapi import AirzoneLocalApi
from aioairzone.mqtt import AirzoneMqttUpdate

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import AIOAIRZONE_DEVICE_TIMEOUT_SEC, DOMAIN

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)

type AirzoneConfigEntry = ConfigEntry[AirzoneUpdateCoordinator]


class AirzoneUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Airzone device."""

    config_entry: AirzoneConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AirzoneConfigEntry,
        airzone: AirzoneLocalApi,
    ) -> None:
        """Initialize."""
        self.airzone = airzone
        self.airzone_lock = Lock()

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        async with self.airzone_lock:
            async with timeout(AIOAIRZONE_DEVICE_TIMEOUT_SEC):
                try:
                    await self.airzone.update()
                except AirzoneError as error:
                    raise UpdateFailed(error) from error

            return self.airzone.data()

    async def async_mqtt_update(self, update: AirzoneMqttUpdate) -> None:
        """Update Airzone data from MQTT."""
        async with self.airzone_lock:
            await self.airzone.mqtt_update(update)
            self.data = self.airzone.data()
            self.async_update_listeners()
