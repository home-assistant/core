"""DataUpdateCoordinator for the Rotarex integration."""

import logging
from datetime import timedelta

from rotarex_dimes_srg_api import InvalidAuth, RotarexApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
    ) -> None:
        """Initialize the data update coordinator."""
        session = async_get_clientsession(hass)
        self.api = RotarexApi(session)
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
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except Exception as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err

    async def _async_update_data(self) -> dict[str, RotarexTank]:
        """Fetch data from API endpoint."""
        try:
            tanks_data = await self.api.fetch_tanks()
        except InvalidAuth as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except Exception as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err

        # Convert to typed dataclasses and index by GUID
        return {
            tank_dict["Guid"]: RotarexTank.from_dict(tank_dict)
            for tank_dict in tanks_data
            if "Guid" in tank_dict
        }
