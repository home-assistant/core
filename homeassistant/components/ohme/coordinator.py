"""Ohme coordinators."""

from datetime import timedelta
import logging

from ohme import ApiException, AuthException, OhmeApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

type OhmeConfigEntry = ConfigEntry[OhmeCoordinator]


class OhmeCoordinator(DataUpdateCoordinator[OhmeApiClient]):
    """Coordinator to pull all updates from the API."""

    config_entry: OhmeConfigEntry

    def __init__(self, hass: HomeAssistant, entry: OhmeConfigEntry) -> None:
        """Initialise coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Ohme Coordinator",
            update_interval=timedelta(seconds=30),
            config_entry=entry,
        )

        self.client: OhmeApiClient = OhmeApiClient(
            self.config_entry.data[CONF_EMAIL], self.config_entry.data[CONF_PASSWORD]
        )
        self._alternative_iteration: bool = True

    async def _async_setup(self) -> None:
        try:
            await self.client.async_login()

            if not await self.client.async_update_device_info():
                raise ConfigEntryNotReady("Unable to get Ohme device information")
        except AuthException as e:
            raise ConfigEntryError("Unable to login to Ohme") from e
        except ApiException as e:
            raise ConfigEntryError(
                "An unexpected response was returned by the API"
            ) from e

    async def _async_update_data(self) -> OhmeApiClient:
        """Fetch data from API endpoint."""
        try:
            await self.client.async_get_charge_session()

            # Fetch on every other update
            if self._alternative_iteration:
                await self.client.async_get_advanced_settings()
        except ApiException as e:
            raise UpdateFailed("Error communicating with API") from e
        else:
            self._alternative_iteration = not self._alternative_iteration

            return self.client
