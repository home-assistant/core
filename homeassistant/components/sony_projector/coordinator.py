"""Data update coordinator for the Sony Projector integration."""

import asyncio
from datetime import timedelta
import logging
from typing import override

import pysdcp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

type SonyProjectorConfigEntry = ConfigEntry[SonyProjectorCoordinator]


class SonyProjectorCoordinator(DataUpdateCoordinator[bool]):
    """Coordinator polling the power state of a projector."""

    config_entry: SonyProjectorConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SonyProjectorConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._projector = pysdcp.Projector(entry.data[CONF_HOST])
        self._lock = asyncio.Lock()

    @override
    async def _async_update_data(self) -> bool:
        """Fetch the power state."""
        # Waiting for a running command would read the state it's about to replace.
        if self._lock.locked():
            return self.data
        async with self._lock:
            try:
                return await self.hass.async_add_executor_job(self._projector.get_power)
            # pySDCP raises bare Exception for timeouts and projector error replies.
            except Exception as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="update_failed",
                ) from err

    async def async_set_power(self, on: bool) -> None:
        """Turn the projector on or off."""
        # A poll still running when the command finishes would overwrite its state.
        async with self._lock:
            try:
                await self.hass.async_add_executor_job(self._projector.set_power, on)
            # pySDCP raises bare Exception for timeouts and projector error replies.
            except Exception as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="power_command_failed",
                ) from err
            # The projector can still report its old state right after a command,
            # so keep the requested state until the next scheduled poll.
            self.async_set_updated_data(on)
