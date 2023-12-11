"""Component to embed Arctic Spa sensors."""

from datetime import timedelta
import logging
from urllib.error import HTTPError

from pyarcticspas import SpaResponse

from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import REQUEST_REFRESH_DELAY
from .hottub import Device

_LOGGER = logging.getLogger(__name__)


class ArcticSpaDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """DataUpdateCoordinator to gather data from the ArcticSpa API."""

    @property
    def status(self) -> SpaResponse:
        """Exposed local Spa status since the underlying API would always call an endpoint."""
        return self._status

    def __init__(self, hass: HomeAssistant, device: Device) -> None:
        """Initialize DataUpdateCoordinator."""
        self.device = device
        self._status = SpaResponse()
        update_interval = timedelta(seconds=REQUEST_REFRESH_DELAY)
        super().__init__(
            hass,
            _LOGGER,
            name="ArcticSpa",
            update_interval=update_interval,
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    async def _async_update_data(self) -> None:
        """Fetch ArcticSpa status from API."""
        try:
            _LOGGER.debug("Requesting async API update")
            self._status = await self.device.api.async_status()
        except HTTPError as e:
            raise UpdateFailed(e) from e
