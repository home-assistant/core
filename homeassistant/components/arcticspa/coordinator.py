"""Component to embed Arctic Spa sensors."""

from datetime import timedelta
import logging

from pyarcticspas import Spa, SpaResponse
from pyarcticspas.error import SpaHTTPException, UnauthorizedError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import REQUEST_REFRESH_COOLDOWN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class ArcticSpaDataUpdateCoordinator(DataUpdateCoordinator[SpaResponse]):
    """DataUpdateCoordinator to gather data from the ArcticSpa API."""

    def __init__(self, hass: HomeAssistant, device: Spa) -> None:
        """Initialize DataUpdateCoordinator."""
        self.device = device
        update_interval = timedelta(seconds=UPDATE_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name="ArcticSpa",
            update_interval=update_interval,
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_COOLDOWN, immediate=False
            ),
        )

    async def _async_update_data(self) -> SpaResponse:
        """Fetch ArcticSpa status from API."""
        try:
            return await self.device.async_status()
        except UnauthorizedError as ex:
            raise ConfigEntryError("Invalid API token") from ex
        except SpaHTTPException as ex:
            raise UpdateFailed(f"{ex.code} {ex.msg}") from ex
