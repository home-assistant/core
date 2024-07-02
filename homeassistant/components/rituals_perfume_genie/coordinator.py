"""The Rituals Perfume Genie data update coordinator."""

import logging

from pyrituals import Diffuser

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class RitualsDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching Rituals Perfume Genie device data from single endpoint."""

    def __init__(self, hass: HomeAssistant, diffuser: Diffuser) -> None:
        """Initialize global Rituals Perfume Genie data updater."""
        self.diffuser = diffuser
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{diffuser.hublot}",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> None:
        """Fetch data from Rituals."""
        await self.diffuser.update_data()
