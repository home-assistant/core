"""SwitchBot Cloud coordinator."""
from logging import getLogger

from async_timeout import timeout
from switchbot_api import CannotConnect, Device, InvalidAuth, Remote, SwitchBotAPI

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = getLogger(__name__)


class SwitchBotCoordinator(DataUpdateCoordinator):
    """SwitchBot Cloud coordinator."""

    _api: SwitchBotAPI
    _device_id: str
    _is_remote = False

    def __init__(
        self, hass: HomeAssistant, api: SwitchBotAPI, device: Device | Remote
    ) -> None:
        """Initialize SwitchBot Cloud."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._api = api
        self._device_id = device.device_id
        self._is_remote = isinstance(device, Remote)

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        if self._is_remote:
            return None
        try:
            _LOGGER.debug("Refreshing %s", self._device_id)
            async with timeout(10):
                status = await self._api.get_status(self._device_id)
                _LOGGER.debug("Refreshing %s with %s", self._device_id, status)
                return status
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed from err
        except CannotConnect as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
