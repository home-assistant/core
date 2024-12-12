"""Ohme coordinators."""

from datetime import timedelta
import logging

from ohme import ApiException, OhmeApiClient

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_EMAIL, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)


class OhmeCoordinator(DataUpdateCoordinator[OhmeApiClient]):
    """Coordinator to pull all updates from the API."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Ohme Coordinator",
            update_interval=timedelta(seconds=30),
        )
        if not self.config_entry:
            raise ConfigEntryError("ConfigEntry was not passed to coordinator")

        self.client: OhmeApiClient = OhmeApiClient(
            self.config_entry.data[CONF_EMAIL], self.config_entry.data[CONF_PASSWORD]
        )
        self._alternative_iteration: bool = True

    async def _async_setup(self) -> None:
        if not await self.client.async_login():
            raise ConfigEntryNotReady("Unable to login to Ohme")

        if not await self.client.async_update_device_info():
            raise ConfigEntryNotReady("Unable to get Ohme device information")

    async def _async_update_data(self) -> OhmeApiClient:
        """Fetch data from API endpoint."""
        try:
            await self.client.async_get_charge_session()

            # Fetch on every other update
            if self._alternative_iteration:
                await self.client.async_get_advanced_settings()

            self._alternative_iteration = not self._alternative_iteration
        except ApiException as e:
            raise UpdateFailed("Error communicating with API") from e
        else:
            return self.client
