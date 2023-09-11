"""Data UpdateCoordinator for the Husqvarna Automower integration."""
import logging

import aioautomower

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AutomowerDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching Husqvarna data."""

    def __init__(
        self, hass: HomeAssistant, implementation, access_token, entry: ConfigEntry
    ) -> None:
        """Initialize data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self.session = aioautomower.AutomowerSession(
            implementation.client_id, access_token, low_energy=False
        )
        self.session.register_token_callback(
            lambda token: hass.config_entries.async_update_entry(
                entry,
                data={"auth_implementation": DOMAIN, CONF_TOKEN: token},
            )
        )

    async def _async_update_data(self) -> None:
        """Fetch data from Husqvarna."""
        try:
            await self.session.connect()
        except Exception as error:
            _LOGGER.debug("Exception in async_setup_entry: %s", error)
            raise UpdateFailed from Exception
