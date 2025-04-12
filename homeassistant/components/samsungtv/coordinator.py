"""Coordinator for the SamsungTV integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .bridge import SamsungTVBridge
from .const import DOMAIN, LOGGER

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
        self.is_on: bool | None = False
        self.async_extra_update: Callable[[], Coroutine[Any, Any, None]] | None = None

    async def _async_update_data(self) -> None:
        """Fetch data from SamsungTV bridge."""
        if self.bridge.auth_failed or self.hass.is_stopping:
            return
        old_state = self.is_on
        if self.bridge.power_off_in_progress:
            self.is_on = False
        else:
            self.is_on = await self.bridge.async_is_on()
        if self.is_on != old_state:
            LOGGER.debug("TV %s state updated to %s", self.bridge.host, self.is_on)

        if self.async_extra_update:
            await self.async_extra_update()
