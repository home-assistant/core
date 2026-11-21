"""Data update coordinator for the Plexilent integration."""

import asyncio
import logging
from typing import Any, override

from pyplexilent import Device, Plexilent, PlexilentAuthError, PlexilentError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type PlexilentConfigEntry = ConfigEntry[PlexilentCoordinator]


class PlexilentCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Poll every device of the account: device id -> last known state."""

    config_entry: PlexilentConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: PlexilentConfigEntry, client: Plexilent
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        # Serializes a poll against a command so an in-flight poll cannot
        # overwrite a just-sent command's result with its stale snapshot.
        self._lock = asyncio.Lock()

    @override
    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch every device and its state from the cloud."""
        try:
            async with self._lock:
                devices = await self.client.devices()
        except PlexilentAuthError as err:
            raise ConfigEntryAuthFailed from err
        except PlexilentError as err:
            raise UpdateFailed(f"Error talking to the Plexilent cloud: {err}") from err
        return {device.id: device for device in devices}

    async def async_command(self, device_id: str, **fields: Any) -> None:
        """Command a device and publish its answer, serialized against polls."""
        async with self._lock:
            device = await self.client.command(device_id, **fields)
            # Keep the next poll on schedule (do not use async_set_updated_data).
            self.data = {**self.data, device_id: device}
            self.async_update_listeners()
