"""Coordinator for Govee Local API."""

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from govee_local_api import GoveeController, GoveeDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_BIND_ADDRESS,
    CONF_DISCOVERY_INTERVAL,
    CONF_DISCOVERY_INTERVAL_DEFAULT,
    CONF_LISENING_PORT,
    CONF_MULTICAST_ADDRESS,
    CONF_TARGET_PORT,
)


class GoveeLocalApiCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: Callable[[Any, GoveeDevice], None],
        scan_interval: timedelta,
        logger: logging.Logger,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass=hass,
            logger=logger,
            name="GoveeLightLocalApi",
            update_interval=scan_interval,
        )

        self._config_entry = config_entry
        config = config_entry.data["config"]

        option_discovery_interval = config_entry.options.get(CONF_DISCOVERY_INTERVAL)
        self._discovery_interval = (
            option_discovery_interval
            if option_discovery_interval
            else config.get(CONF_DISCOVERY_INTERVAL, CONF_DISCOVERY_INTERVAL_DEFAULT)
        )

        def discovery_callback(device: GoveeDevice, is_new: bool) -> bool:
            if is_new:
                async_add_entities(self, device)
            return True

        self._controller = GoveeController(
            loop=hass.loop,
            logger=logger,
            listening_address=config[CONF_BIND_ADDRESS],
            broadcast_address=config[CONF_MULTICAST_ADDRESS],
            broadcast_port=config[CONF_TARGET_PORT],
            listening_port=config[CONF_LISENING_PORT],
            discovery_enabled=True,
            discovery_interval=config[CONF_DISCOVERY_INTERVAL],
            discovered_callback=discovery_callback,
            update_enabled=False,
        )

    async def start(self) -> None:
        """Start the Govee coordinator."""
        await self._controller.start()
        self._controller.send_update_message()

    def clenaup(self) -> None:
        """Stop and clenaup the cooridinator."""
        self._controller.clenaup()

    async def turn_on(self, device: GoveeDevice) -> None:
        """Turn on the light."""
        assert self._controller == device.controller
        await device.turn_on()

    async def turn_off(self, device: GoveeDevice) -> None:
        """Turn off the light."""
        assert self._controller == device.controller
        await device.turn_off()

    async def set_brightness(self, device: GoveeDevice, brightness: int) -> None:
        """Set light brightness."""
        assert self._controller == device.controller
        await device.set_brightness(brightness)

    async def set_rgb_color(
        self, device: GoveeDevice, red: int, green: int, blue: int
    ) -> None:
        """Set light RGB color."""
        assert self._controller == device.controller
        await device.set_rgb_color(red, green, blue)

    async def set_temperature(self, device: GoveeDevice, temperature: int) -> None:
        """Set light color in kelvin."""
        assert self._controller == device.controller
        await device.set_temperature(temperature)

    @property
    def devices(self) -> list[GoveeDevice]:
        """Return a list of discovered Govee devices."""
        return self._controller.devices

    async def _async_update_data(self):
        discovery_interval = self._config_entry.options.get(CONF_DISCOVERY_INTERVAL)
        if discovery_interval and discovery_interval != self._discovery_interval:
            self._controller.set_discovery_interval(discovery_interval)
            self.logger.debug(
                "Changed update interval from %d to %d",
                self._discovery_interval,
                discovery_interval,
            )
            self._discovery_interval = discovery_interval
        self._controller.send_update_message()
        return self._controller.devices
