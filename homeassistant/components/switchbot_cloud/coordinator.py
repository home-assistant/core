"""SwitchBot Cloud coordinator."""

from asyncio import timeout
from logging import getLogger
from typing import Any

from switchbot_api import CannotConnect, Device, Remote, SwitchBotAPI

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = getLogger(__name__)

type Status = dict[str, Any] | None


class SwitchBotCoordinator(DataUpdateCoordinator[Status]):
    """SwitchBot Cloud coordinator."""

    _api: SwitchBotAPI
    _device_id: str

    def __init__(
        self, hass: HomeAssistant, api: SwitchBotAPI, device: Device | Remote
    ) -> None:
        """Initialize SwitchBot Cloud."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._api = api
        self._device_id = device.device_id
        self._should_poll = not isinstance(device, Remote)

    async def _async_update_data(self) -> Status:
        """Fetch data from API endpoint."""
        if not self._should_poll:
            return None
        try:
            _LOGGER.debug("Refreshing %s", self._device_id)
            async with timeout(10):
                status: Status = await self._api.get_status(self._device_id)
                _LOGGER.debug("Refreshing %s with %s", self._device_id, status)
                return status
        except CannotConnect as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
