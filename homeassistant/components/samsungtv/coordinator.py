"""Coordinator for the SamsungTV integration."""

from collections.abc import Callable, Coroutine
from datetime import timedelta
from typing import Any, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_METHOD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .bridge import SamsungTVBridge
from .const import (
    CONF_SSDP_RENDERING_CONTROL_LOCATION,
    DOMAIN,
    LOGGER,
    METHOD_WEBSOCKET,
)
from .dmr import async_probe_rendering_control_location

SCAN_INTERVAL = 10

type SamsungTVConfigEntry = ConfigEntry[SamsungTVDataUpdateCoordinator]


class SamsungTVDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for the SamsungTV integration."""

    config_entry: SamsungTVConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SamsungTVConfigEntry,
        bridge: SamsungTVBridge,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

        self.bridge = bridge
        self.is_on: bool | None = None
        self.async_extra_update: Callable[[], Coroutine[Any, Any, None]] | None = None

    @override
    async def _async_update_data(self) -> None:
        """Fetch data from SamsungTV bridge."""
        if self.bridge.auth_failed:
            return
        old_state = self.is_on
        if self.bridge.power_off_in_progress:
            self.is_on = False
        else:
            self.is_on = await self.bridge.async_is_on()
        if self.is_on != old_state:
            LOGGER.debug(
                "TV %s state updated from %s to %s",
                self.bridge.host,
                old_state,
                self.is_on,
            )

        if self.is_on and old_state is False:
            await self._async_probe_rendering_control_location()

        if self.async_extra_update:
            await self.async_extra_update()

    async def _async_probe_rendering_control_location(self) -> None:
        """Look for a renderer that wasn't found at setup, now that the TV is on."""
        data = self.config_entry.data
        host = data[CONF_HOST]
        if data[CONF_METHOD] != METHOD_WEBSOCKET or data.get(
            CONF_SSDP_RENDERING_CONTROL_LOCATION
        ):
            return
        location = await async_probe_rendering_control_location(self.hass, host)
        # The entry may have been updated (token, SSDP) while the probe was running
        data = self.config_entry.data
        if (
            location
            and data[CONF_HOST] == host
            and not data.get(CONF_SSDP_RENDERING_CONTROL_LOCATION)
        ):
            # Saving the location reloads the entry, which sets up the renderer
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**data, CONF_SSDP_RENDERING_CONTROL_LOCATION: location},
            )
