"""Coordinator for TheSilentWave integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from pysilentwave import SilentWaveClient
from pysilentwave.exceptions import SilentWaveError

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=10)

# Type alias for config entry with coordinator
type TheSilentWaveConfigEntry = ConfigEntry[TheSilentWaveCoordinator]


class TheSilentWaveCoordinator(DataUpdateCoordinator):
    """Class to manage fetching the data from the API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the coordinator."""
        websession = async_get_clientsession(hass)
        self.entry = entry
        self._device_name = entry.data["name"]
        self._host = entry.data["host"]
        self.client = SilentWaveClient(self._host, session=websession)

        # Store the name directly to be accessed by entities.
        self._device_name = self._device_name
        self._host = self._host

        # Track connection state to avoid log spam.
        self.has_connection = True
        self._connection_error_logged = False

        super().__init__(
            hass,
            _LOGGER,
            name=self._device_name,
            update_interval=UPDATE_INTERVAL,
        )

    @property
    def device_name(self):
        """Return the name of the device."""
        return self._device_name

    @property
    def host(self) -> str:
        """Return the host address."""
        return self._host

    async def _async_update_data(self):
        """Fetch data from the API."""
        try:
            status = await self.client.get_status()

            # Reset connection tracking state if needed
            if not self.has_connection:
                self.has_connection = True
                self._connection_error_logged = False

        except SilentWaveError as exc:
            # Mark that we have a connection issue.
            self.has_connection = False

            # Only log the error once until we reconnect.
            if not self._connection_error_logged:
                _LOGGER.error("Failed to connect to device at %s", self._host)
                self._connection_error_logged = True

            raise UpdateFailed("Failed to fetch device status") from exc
        else:
            return status
