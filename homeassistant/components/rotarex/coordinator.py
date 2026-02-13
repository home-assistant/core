"""DataUpdateCoordinator for the Rotarex integration."""

from datetime import timedelta
import logging

from rotarex_dimes_srg_api import InvalidAuth, RotarexApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .models import RotarexTank

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)


class RotarexDataUpdateCoordinator(DataUpdateCoordinator[dict[str, RotarexTank]]):
    """Class to manage fetching Rotarex data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: RotarexApi,
    ) -> None:
        """Initialize the data update coordinator."""
        self.api = api
        self._email = config_entry.data[CONF_EMAIL]
        self._password = config_entry.data[CONF_PASSWORD]
        self.api.set_credentials(self._email, self._password)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )

    async def _async_setup(self) -> None:
        """Set up the coordinator with initial authentication check."""
        try:
            await self.api.login(self._email, self._password)
        except InvalidAuth as err:
            raise ConfigEntryError(
                f"Authentication failed: {err}"
            ) from err

    async def _async_update_data(self) -> dict[str, RotarexTank]:
        """Fetch data from API endpoint."""
        try:
            tanks_data = await self.api.fetch_tanks()
        except InvalidAuth as err:
            _LOGGER.warning("Token expired, attempting to re-login: %s", err)
            try:
                await self.api.login(self._email, self._password)
            except InvalidAuth as login_err:
                raise ConfigEntryError(
                    f"Re-authentication failed: {login_err}"
                ) from login_err
            # If re-login succeeds, try fetch_tanks again
            try:
                tanks_data = await self.api.fetch_tanks()
            except InvalidAuth as fetch_err:
                raise ConfigEntryError(
                    f"Authentication failed after re-login: {fetch_err}"
                ) from fetch_err

        # Convert to typed dataclasses and index by GUID
        return {
            tank_dict["Guid"]: RotarexTank.from_dict(tank_dict)
            for tank_dict in tanks_data
            if "Guid" in tank_dict
        }
