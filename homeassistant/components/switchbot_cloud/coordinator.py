"""SwitchBot Cloud coordinator."""

from asyncio import timeout
from logging import getLogger
from typing import Any

from switchbot_api import CannotConnect, Device, Remote, SwitchBotAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = getLogger(__name__)

type Status = dict[str, Any] | None


class SwitchBotCoordinator(DataUpdateCoordinator[Status]):
    """SwitchBot Cloud coordinator."""

    config_entry: ConfigEntry
    _api: SwitchBotAPI
    _device_id: str

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: SwitchBotAPI,
        device: Device | Remote,
        update_by_webhook: bool,
    ) -> None:
        """Initialize SwitchBot Cloud."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._api = api
        self._device_id = device.device_id
        self._should_poll = not update_by_webhook and not isinstance(device, Remote)
        self._update_by_webhook = update_by_webhook
        self._need_initialized = update_by_webhook

    def update_by_webhook(self) -> bool:
        """Return update_by_webhook value."""
        return self._update_by_webhook

    async def _async_update_data(self) -> Status:
        """Fetch data from API endpoint."""
        if not self._should_poll and not self._need_initialized:
            return None

        self._need_initialized = False
        try:
            _LOGGER.debug("Refreshing %s", self._device_id)
            async with timeout(10):
                status: Status = await self._api.get_status(self._device_id)
                _LOGGER.debug("Refreshing %s with %s", self._device_id, status)
                return status
        except CannotConnect as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
