"""Data update coordinator for Dreo devices."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, NotRequired, TypedDict

from hscloud.const import DEVICE_TYPE, FAN_DEVICE
from hscloud.hscloud import HsCloud
from hscloud.hscloudexception import HsCloudException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


class DreoBaseDeviceData(TypedDict):
    """Base data for all Dreo devices."""

    available: bool
    is_on: bool


class DreoFanDeviceData(DreoBaseDeviceData):
    """Data specific to Dreo fan devices."""

    mode: NotRequired[str | None]
    oscillate: NotRequired[bool | None]
    speed: NotRequired[int | None]


# Use pipe syntax for type annotations
DreoDeviceDataType = DreoFanDeviceData


class DreoDataUpdateCoordinator(DataUpdateCoordinator[DreoDeviceDataType]):
    """Class to manage fetching Dreo data."""

    def __init__(self, hass: HomeAssistant, client: HsCloud, device_id: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.device_id = device_id
        self.device_model: str | None = None
        self.device_type: str | None = None
        # Initialize with a fan device data structure with required fields
        self.data: DreoFanDeviceData = {"available": False, "is_on": False}

    def _get_device_type(self) -> str | None:
        """Determine device type based on model."""
        if not self.device_model:
            return None
        return DEVICE_TYPE.get(self.device_model)

    async def _async_update_data(self) -> DreoDeviceDataType:
        """Update data via library."""
        # Create fan data structure with minimum required fields
        fan_data: DreoFanDeviceData = {"available": False, "is_on": False}

        try:
            # Get device status
            status = await self._async_get_status()

            if status is None:
                return fan_data

            # Update device model and type information
            if not self.device_model and "model" in status:
                self.device_model = status.get("model")
                self.device_type = self._get_device_type()

            # Set common properties
            fan_data["available"] = status.get("connected", False)
            fan_data["is_on"] = status.get("power_switch", False)

            # Fill specific properties based on device type
            device_type = self.device_type or self._get_device_type()

            if device_type == FAN_DEVICE.get("type"):
                # Fan device data
                if "mode" in status:
                    fan_data["mode"] = status.get("mode")

                if "oscillate" in status:
                    fan_data["oscillate"] = status.get("oscillate")

                if "speed" in status:
                    fan_data["speed"] = status.get("speed")

                return fan_data

        except HsCloudException as error:
            raise UpdateFailed(f"Error communicating with Dreo API: {error}") from error
        except Exception as error:  # pylint: disable=broad-except
            # We need to catch all exceptions to ensure the coordinator doesn't break
            # This is intentional to handle any unforeseen errors from the API
            raise UpdateFailed(f"Unexpected error: {error}") from error

        # Return fan data if device type cannot be determined or other issues occur
        return fan_data

    async def _async_get_status(self) -> dict[str, Any] | None:
        """Get device status with error handling."""
        try:
            return await self.hass.async_add_executor_job(
                self.client.get_status, self.device_id
            )
        except HsCloudException as error:
            _LOGGER.error("Error getting device status: %s", error)
            return None
        # Catch specific exceptions instead of a blind Exception
        except (ConnectionError, TimeoutError, ValueError) as error:
            _LOGGER.error("Unexpected error getting device status: %s", error)
            return None
