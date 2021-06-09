"""DataUpdateCoordinator for WLED."""

from wled import WLED, Device as WLEDDevice, WLEDError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL


class WLEDDataUpdateCoordinator(DataUpdateCoordinator[WLEDDevice]):
    """Class to manage fetching WLED data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
    ) -> None:
        """Initialize global WLED data updater."""
        self.wled = WLED(host, session=async_get_clientsession(hass))

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    def update_listeners(self) -> None:
        """Call update on all listeners."""
        for update_callback in self._listeners:
            update_callback()

    async def _async_update_data(self) -> WLEDDevice:
        """Fetch data from WLED."""
        try:
            return await self.wled.update(full_update=not self.last_update_success)
        except WLEDError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
