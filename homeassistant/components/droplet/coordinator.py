"""Droplet device data update coordinator object."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import time

from pydroplet.droplet import Droplet

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CODE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, RECONNECT_DELAY

ML_L_CONVERSION = 1000
VERSION_TIMEOUT = 5

_LOGGER = logging.getLogger(__name__)


type DropletConfigEntry = ConfigEntry[DropletDataCoordinator]


class DropletDataCoordinator(DataUpdateCoordinator[None]):
    """Droplet device object."""

    config_entry: DropletConfigEntry
    unsub: Callable | None

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

    async def _async_update_data(self) -> None:
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

    async def setup(self) -> bool:
        """Set up droplet client."""

        async def listen() -> None:
            """Listen for state changes via WebSocket."""
            while True:
                connected = await self.droplet.connect()
                if connected:
                    # This will only return if there was a broken connection
                    await self.droplet.listen(callback=self.async_set_updated_data)

                self.async_set_updated_data(None)
                await asyncio.sleep(RECONNECT_DELAY)

        async def disconnect(_: Event) -> None:
            """Close WebSocket connection."""
            self.unsub = None
            await self.droplet.disconnect()

        # Clean disconnect WebSocket on Home Assistant shutdown
        self.unsub = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, disconnect
        )
        self.config_entry.async_create_background_task(
            self.hass, listen(), "droplet-listen"
        )
        return True

    def get_volume_delta(self) -> float:
        """Get volume since the last point."""
        return self.droplet.get_volume_delta() / ML_L_CONVERSION

    def get_flow_rate(self) -> float:
        """Retrieve Droplet's latest flow rate."""
        return self.droplet.get_flow_rate()

    def get_availability(self) -> bool:
        """Retrieve Droplet's availability status."""
        return self.droplet.get_availability()

    def get_server_status(self) -> str:
        """Retrieve Droplet's connection status to Hydrific servers."""
        return self.droplet.get_server_status()

    def get_signal_quality(self) -> str:
        """Retrieve Droplet's signal quality."""
        return self.droplet.get_signal_quality()
