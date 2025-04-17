"""Data update coordinator for Dreo devices."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import NotRequired, TypedDict

from hscloud.hscloudexception import HsCloudException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


class DreoDeviceData(TypedDict):
    """Dreo device data."""

    available: bool
    is_on: bool
    mode: NotRequired[str | None]
    oscillate: NotRequired[bool | None]
    speed: NotRequired[int | None]
    temperature: NotRequired[float | None]
    humidity: NotRequired[float | None]


class DreoDataUpdateCoordinator(DataUpdateCoordinator[DreoDeviceData]):
    """Class to manage fetching Dreo data."""

    def __init__(self, hass: HomeAssistant, client, device_id: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.device_id = device_id
        self.data: DreoDeviceData = {"available": False, "is_on": False}

    async def _async_update_data(self) -> DreoDeviceData:
        """Update data via library."""
        data: DreoDeviceData = {"available": False, "is_on": False}

        try:
            # Use the client to get status for the specific device
            status = await self.hass.async_add_executor_job(
                self.client.get_status, self.device_id
            )

            if status is None:
                return data

            data["available"] = status.get("connected", False)
            data["is_on"] = status.get("power_switch", False)

            if "mode" in status:
                data["mode"] = status.get("mode")

            if "oscillate" in status:
                data["oscillate"] = status.get("oscillate")

            if "speed" in status:
                data["speed"] = status.get("speed")

        except HsCloudException as error:
            raise UpdateFailed(f"Error communicating with Dreo API: {error}") from error
        except Exception as error:
            raise UpdateFailed(f"Unexpected error: {error}") from error

        return data
