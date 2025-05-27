"""Coordinator for TheSilentWave integration."""

from datetime import timedelta
import logging

from pysilentwave import SilentWaveClient
from pysilentwave.exceptions import SilentWaveError

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.config_entries import ConfigEntry

# Type alias for config entry with coordinator
TheSilentWaveConfigEntry = ConfigEntry["TheSilentWaveCoordinator"]

_LOGGER = logging.getLogger(__name__)


class TheSilentWaveCoordinator(DataUpdateCoordinator):
    """Class to manage fetching the data from the API."""

    def __init__(self, hass, name, host, scan_interval):
        """Initialize the coordinator."""
        websession = async_get_clientsession(hass)
        self.client = SilentWaveClient(host, session=websession)

        # Store the name directly to be accessed by entities.
        self._device_name = name
        self._host = host

        # Track connection state to avoid log spam.
        self._has_connection = True
        self._connection_error_logged = False

        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=scan_interval),
        )

    @property
    def device_name(self):
        """Return the name of the device."""
        return self._device_name

    async def _async_update_data(self):
        """Fetch data from the API."""
        try:
            status = await self.client.get_status()

            # If we previously had a connection error and now succeeded, log recovery.
            if not self._has_connection:
                _LOGGER.info("Reconnected to device at %s", self._host)
                self._has_connection = True
                self._connection_error_logged = False

        except SilentWaveError as exc:
            # Mark that we have a connection issue.
            self._has_connection = False

            # Only log the error once until we reconnect.
            if not self._connection_error_logged:
                _LOGGER.error("Failed to connect to device at %s", self._host)
                self._connection_error_logged = True

            raise UpdateFailed("Failed to fetch device status") from exc
        else:
            return status
