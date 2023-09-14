"""Data UpdateCoordinator for the Husqvarna Automower integration."""
import logging

import aioautomower

from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AutomowerDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching Husqvarna data."""

    def __init__(
        self,
        hass: HomeAssistant,
        implementation,
        session: OAuth2Session,
    ) -> None:
        """Initialize data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self.session = aioautomower.AutomowerSession(
            implementation.client_id,
            session.token,
            low_energy=False,
            handle_token=False,
        )

    async def _async_update_data(self) -> None:
        """Fetch data from Husqvarna."""
        try:
            await self.session.connect()
        except Exception as error:
            _LOGGER.debug("Exception in async_setup_entry: %s", error)
            raise UpdateFailed from Exception
