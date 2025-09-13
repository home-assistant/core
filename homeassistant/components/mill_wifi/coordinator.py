"""Data coordinator file."""

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MillApiClient
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class MillDataCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Data coordinator class."""

    def __init__(self, hass: HomeAssistant, api: MillApiClient):
        """Coordinator initialization."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_data_coordinator",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, dict]:
        try:
            devices_list = await self.api.get_all_devices()
            devices_dict = {}
            if devices_list:
                for device in devices_list:
                    if device and device.get("deviceId"):
                        devices_dict[device["deviceId"]] = device
                    else:
                        _LOGGER.warning(
                            "Found an invalid device entry in list: %s", device
                        )
            return devices_dict  # noqa: TRY300
        except Exception as err:
            _LOGGER.error("Error fetching devices in coordinator: %s", err)
            raise UpdateFailed(f"Error fetching devices: {err}") from err
