"""Droplet device data update coordinator object."""

from __future__ import annotations

import asyncio
import logging
import time

from pydroplet.droplet import Droplet

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CODE, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONNECT_DELAY, DOMAIN

VERSION_TIMEOUT = 5

_LOGGER = logging.getLogger(__name__)

TIMEOUT = 1

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
            host=entry.data[CONF_IP_ADDRESS],
            port=entry.data[CONF_PORT],
            token=entry.data[CONF_CODE],
            session=async_get_clientsession(self.hass),
            logger=_LOGGER,
        )
        assert entry.unique_id is not None
        self.unique_id = entry.unique_id

    async def _async_setup(self) -> None:
        if not await self.setup():
            raise ConfigEntryNotReady("Device is offline")

        # Droplet should send its metadata within 5 seconds
        end = time.time() + VERSION_TIMEOUT
        while not self.droplet.version_info_available():
            await asyncio.sleep(TIMEOUT)
            if time.time() > end:
                _LOGGER.warning("Failed to get version info from Droplet")
                return

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
            self.droplet.listen_forever(CONNECT_DELAY, self.async_set_updated_data),
            "droplet-listen",
        )
        end = time.time() + CONNECT_DELAY
        while time.time() < end:
            if self.droplet.connected:
                return True
            await asyncio.sleep(TIMEOUT)
        return False

    def get_availability(self) -> bool:
        """Retrieve Droplet's availability status."""
        return self.droplet.get_availability()
