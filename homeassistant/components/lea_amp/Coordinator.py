"""Coordinator for LEA AMP local."""

import asyncio
from collections.abc import Callable
import logging

from controller import IP_ADDRESS, LeaController, LeaZone

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .constlea import CONNECTION_TIMEOUT, PORT, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type LEAAMPConfigEntry = ConfigEntry[LEAAMPApiCoordinator]


class LEAAMPApiCoordinator(DataUpdateCoordinator[list[LeaZone]]):
    """LEA AMP local coordinator."""

    config_entry: LEAAMPConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: LEAAMPConfigEntry) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name="LeaAMP",
            update_interval=SCAN_INTERVAL,
        )

        self._controller = LeaController(
            loop=hass.loop,
            port=PORT,
            ip_address=IP_ADDRESS,
            discovery_enabled=True,
            discovery_interval=CONNECTION_TIMEOUT,
            discovered_callback=None,
            update_enabled=False,
        )

    async def start(self) -> None:
        """Start the Govee coordinator."""
        await self._controller.start()
        self._controller.send_update_message()

    async def set_discovery_callback(
        self, callback: Callable[[LeaZone, bool], bool]
    ) -> None:
        """Set discovery callback for automatic LEA AMP discovery."""
        self._controller.set_zone_discovered_callback(callback)

    def cleanup(self) -> asyncio.Event:
        """Stop and cleanup the cooridinator."""
        return self._controller.cleanup()

    async def turn_on(self, zone: LeaZone) -> None:
        """Turn on the zone."""
        await zone.set_zone_power(True)

    async def turn_off(self, zone: LeaZone) -> None:
        """Turn off the zone."""
        await zone.set_zone_power(False)

    async def send_key_command(self, zone: LeaZone, command: str) -> None:
        """Send Key Command."""
        if "VOLUME_DOWN" in command:
            current_volume = zone.volume
            current_volume = int(current_volume) - 1
            await self.set_volume(zone, current_volume)
        elif "VOLUME_UP" in command:
            current_volume = zone.volume
            current_volume = int(current_volume) + 1
            await self.set_volume(zone, current_volume)
        elif "MUTE" in command:
            current_mute = zone.mute
            if current_mute:
                await self.set_mute(zone, False)
            else:
                await self.set_mute(zone, True)

    async def set_volume(self, zone: LeaZone, volume: int) -> None:
        """Set zone volume."""
        await zone.set_zone_volume(volume)

    async def set_mute(self, zone: LeaZone, mute: bool) -> None:
        """Set zone mute."""
        await zone.set_zone_mute(mute)

    async def set_source(self, zone: LeaZone, source: int) -> None:
        """Set light scene."""
        await zone.set_zone_source(source)

    @property
    def zones(self) -> list[LeaZone]:
        """Return a list of discovered Govee zones."""
        return self._controller.zones

    async def _async_update_data(self) -> list[LeaZone]:
        self._controller.send_update_message()
        return self._controller.zones
