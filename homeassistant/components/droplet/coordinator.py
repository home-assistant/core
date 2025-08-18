"""Droplet device data update coordinator object."""

from __future__ import annotations

import asyncio
import logging
import time

from pydroplet.droplet import Droplet

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, RECONNECT_DELAY

ML_L_CONVERSION = 1000
VERSION_TIMEOUT = 5

_LOGGER = logging.getLogger(__name__)


type DropletConfigEntry = ConfigEntry[DropletDataCoordinator]


class DropletDataCoordinator(DataUpdateCoordinator[None]):
    """Droplet device object."""

    config_entry: DropletConfigEntry

    def __init__(self, hass: HomeAssistant, entry: DropletConfigEntry) -> None:
        """Initialize the device."""
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=f"{DOMAIN}-{entry.unique_id}"
        )
        self.droplet = Droplet(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            token=entry.data[CONF_CODE],
            session=async_get_clientsession(self.hass),
            logger=_LOGGER,
        )
        self.dev_info = DeviceInfo()

    async def _async_setup(self) -> None:
        if not await self.setup():
            raise ConfigEntryNotReady("Device is offline")

        # Droplet should send its metadata within 5 seconds
        end = time.time() + VERSION_TIMEOUT
        assert self.config_entry.unique_id is not None
        self.dev_info = DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.unique_id)},
            name=self.config_entry.data[CONF_NAME],
        )
        while not self.droplet.version_info_available():
            await asyncio.sleep(1)
            if time.time() > end:
                _LOGGER.warning("Failed to get version info from Droplet")
                return
        self.dev_info.update(
            DeviceInfo(
                manufacturer=self.droplet.get_manufacturer(),
                model=self.droplet.get_model(),
                sw_version=self.droplet.get_fw_version(),
                serial_number=self.droplet.get_sn(),
            )
        )

    async def _async_update_data(self) -> None:
        if not self.droplet.connected:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="connection_error"
            )

    async def setup(self) -> bool:
        """Set up droplet client."""
        self.config_entry.async_on_unload(self.droplet.stop_listening)
        self.config_entry.async_create_background_task(
            self.hass,
            self.droplet.listen_forever(RECONNECT_DELAY, self.async_set_updated_data),
            "droplet-listen",
        )
        return True

    def get_availability(self) -> bool:
        """Retrieve Droplet's availability status."""
        return self.droplet.get_availability()
