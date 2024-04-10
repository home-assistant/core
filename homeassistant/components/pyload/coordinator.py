"""Update coordinator for pyLoad Integration."""

from datetime import timedelta
import logging

from pyloadapi.api import PyLoadAPI
from pyloadapi.exceptions import CannotConnect, InvalidAuth

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


class PyLoadCoordinator(DataUpdateCoordinator):
    """pyLoad coordinator."""

    def __init__(self, hass: HomeAssistant, pyload: PyLoadAPI) -> None:
        """Initialize pyLoad coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.pyload = pyload

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            return await self.pyload.get_status()
        except InvalidAuth:
            try:
                await self.pyload.login()
            except InvalidAuth as e:
                raise ConfigEntryAuthFailed from e
        except CannotConnect as e:
            raise UpdateFailed(f"Error communicating with API: {e}") from e
