"""Define the Nanoleaf data coordinator."""

from datetime import timedelta
import logging

from aionanoleaf import InvalidToken, Nanoleaf, Unavailable

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class NanoleafCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching Nanoleaf data."""

    def __init__(self, hass: HomeAssistant, nanoleaf: Nanoleaf) -> None:
        """Initialize the Nanoleaf data coordinator."""
        super().__init__(
            hass, _LOGGER, name="Nanoleaf", update_interval=timedelta(minutes=1)
        )
        self.nanoleaf = nanoleaf

    async def _async_update_data(self) -> None:
        try:
            await self.nanoleaf.get_info()
        except Unavailable as err:
            raise UpdateFailed from err
        except InvalidToken as err:
            raise ConfigEntryAuthFailed from err
