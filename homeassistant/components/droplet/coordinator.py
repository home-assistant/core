"""Droplet device data update coordinator object."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_HOST, CONF_PAIRING_CODE, CONF_PORT, DOMAIN, RECONNECT_DELAY
from .dropletmqtt import Droplet

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
            token=entry.data[CONF_PAIRING_CODE],
            session=async_get_clientsession(self.hass),
            logger=_LOGGER,
        )

    async def setup(self) -> bool:
        """Set up droplet client."""
        if not await self.droplet.connect():
            return False

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
