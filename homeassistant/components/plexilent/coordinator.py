"""Data update coordinator for the Plexilent integration."""

import logging
from typing import override

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

    @override
    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch every device and its state from the cloud."""
        try:
            devices = await self.client.devices()
        except PlexilentAuthError as err:
            raise ConfigEntryAuthFailed from err
        except PlexilentError as err:
            raise UpdateFailed(f"Error talking to the Plexilent cloud: {err}") from err
        return {device.id: device for device in devices}
