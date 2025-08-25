"""Coordinator for DayBetter light local."""

import asyncio
from collections.abc import Callable
import logging

from daybetter_local_api import DayBetterController, DayBetterDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_DISCOVERY_INTERVAL_DEFAULT,
    CONF_LISTENING_PORT_DEFAULT,
    CONF_MULTICAST_ADDRESS_DEFAULT,
    CONF_TARGET_PORT_DEFAULT,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type DayBetterLocalConfigEntry = ConfigEntry["DayBetterLocalApiCoordinator"]


class DayBetterLocalApiCoordinator(DataUpdateCoordinator[list[DayBetterDevice]]):
    """DayBetter light local coordinator."""

    config_entry: DayBetterLocalConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: DayBetterLocalConfigEntry
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name="DayBetterLightLocalApi",
            update_interval=SCAN_INTERVAL,
        )

        host = config_entry.data.get("host")
        if not host:
            raise ConfigEntryNotReady("Missing host in config entry")

        self._controller = DayBetterController(
            loop=hass.loop,
            logger=_LOGGER,
            listening_address=host,
            broadcast_address=CONF_MULTICAST_ADDRESS_DEFAULT,
            broadcast_port=CONF_TARGET_PORT_DEFAULT,
            listening_port=CONF_LISTENING_PORT_DEFAULT,
            discovery_enabled=True,
            discovery_interval=CONF_DISCOVERY_INTERVAL_DEFAULT,
            discovered_callback=None,
            update_enabled=False,
        )

    async def start(self) -> None:
        """Start the controller and trigger discovery."""
        await self._controller.start()
        self._controller.send_discovery_message()

    async def set_discovery_callback(
        self, callback: Callable[[DayBetterDevice, bool], bool]
    ) -> None:
        """Set discovery callback for automatic device discovery."""
        self._controller.set_device_discovered_callback(callback)

    def cleanup(self) -> asyncio.Event:
        """Stop and cleanup the controller. Returns an asyncio.Event when done."""
        return self._controller.cleanup()

    @property
    def devices(self) -> list[DayBetterDevice]:
        """Return currently known devices (from latest refresh)."""
        return self.data or list(self._controller.devices or [])

    async def _async_update_data(self) -> list[DayBetterDevice]:
        """Update device data from the controller."""
        self._controller.send_update_message()
        await asyncio.sleep(0.5)  # FIXME: could be improved with event/wait_for
        return list(self._controller.devices or [])
