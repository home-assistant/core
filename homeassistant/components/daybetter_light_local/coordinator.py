"""Coordinator for DayBetter light local."""

import asyncio
from collections.abc import Callable
import logging

from daybetter_local_api import DayBetterController, DayBetterDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_DISCOVERY_INTERVAL_DEFAULT,
    CONF_LISTENING_PORT_DEFAULT,
    CONF_MULTICAST_ADDRESS_DEFAULT,
    CONF_TARGET_PORT_DEFAULT,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type DayBetterLocalConfigEntry = ConfigEntry[DayBetterLocalApiCoordinator]


class DayBetterLocalApiCoordinator(DataUpdateCoordinator[list[DayBetterDevice]]):
    """DayBetter light local coordinator."""

    config_entry: DayBetterLocalConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: DayBetterLocalConfigEntry
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name="DayBetterLightLocalApi",
            update_interval=SCAN_INTERVAL,
        )

        self._controller = DayBetterController(
            loop=hass.loop,
            logger=_LOGGER,
            broadcast_address=CONF_MULTICAST_ADDRESS_DEFAULT,
            broadcast_port=CONF_TARGET_PORT_DEFAULT,
            listening_port=CONF_LISTENING_PORT_DEFAULT,
            discovery_enabled=True,
            discovery_interval=CONF_DISCOVERY_INTERVAL_DEFAULT,
            discovered_callback=None,
            update_enabled=False,
        )

    async def start(self) -> None:
        """Start the DayBetter coordinator."""
        await self._controller.start()
        self._controller.send_update_message()

    async def set_discovery_callback(
        self, callback: Callable[[DayBetterDevice, bool], bool]
    ) -> None:
        """Set discovery callback for automatic DayBetter light discovery."""
        self._controller.set_device_discovered_callback(callback)

    def cleanup(self) -> asyncio.Event:
        """Stop and cleanup the cooridinator."""
        return self._controller.cleanup()

    async def turn_on(self, device: DayBetterDevice) -> None:
        """Turn on the light."""
        await device.turn_on()

    async def turn_off(self, device: DayBetterDevice) -> None:
        """Turn off the light."""
        await device.turn_off()

    async def set_brightness(self, device: DayBetterDevice, brightness: int) -> None:
        """Set light brightness."""
        await device.set_brightness(brightness)

    async def set_rgb_color(
        self, device: DayBetterDevice, red: int, green: int, blue: int
    ) -> None:
        """Set light RGB color."""
        await device.set_rgb_color(red, green, blue)

    async def set_temperature(self, device: DayBetterDevice, temperature: int) -> None:
        """Set light color in kelvin."""
        await device.set_temperature(temperature)

    async def set_scene(self, device: DayBetterController, scene: str) -> None:
        """Set light scene."""
        await device.set_scene(scene)

    @property
    def devices(self) -> list[DayBetterDevice]:
        """Return a list of discovered DayBetter devices."""
        return self._controller.devices

    async def _async_update_data(self) -> list[DayBetterDevice]:
        self._controller.send_update_message()
        return self._controller.devices
