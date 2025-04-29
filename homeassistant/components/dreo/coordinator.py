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
from homeassistant.util.percentage import ranged_value_to_percentage

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


class DreoGenericDeviceData(TypedDict):
    """Base data for all Dreo devices."""

    available: bool
    is_on: bool


class DreoFanDeviceData(DreoGenericDeviceData):
    """Data specific to Dreo fan devices."""

    mode: NotRequired[str]
    oscillate: NotRequired[bool]
    speed_percentage: NotRequired[int]


DreoDeviceData = DreoFanDeviceData | DreoGenericDeviceData


class DeviceDataFactory:
    """Factory to create device data based on device type."""

    @staticmethod
    def create_data(
        coordinator: DreoDataUpdateCoordinator,
        base_data: DreoGenericDeviceData,
        status: dict[str, Any],
    ) -> DreoDeviceData:
        """Create appropriate device data based on device type."""
        if (
            coordinator.device_type == FAN_DEVICE.get("type")
            and coordinator.device_model
        ):
            return FanDataStrategy.process_data(
                coordinator.device_model, base_data, status
            )
        return DreoFanDeviceData(**base_data)


class FanDataStrategy:
    """Strategy for processing fan device data."""

    @staticmethod
    def process_data(
        device_model: str, base_data: DreoGenericDeviceData, status: dict[str, Any]
    ) -> DreoFanDeviceData:
        """Process fan device specific data."""
        # Initialize with required fields
        fan_data = DreoFanDeviceData(
            available=base_data["available"],
            is_on=base_data["is_on"],
        )

        if "mode" in status:
            fan_data["mode"] = str(status.get("mode", ""))

        if "oscillate" in status:
            fan_data["oscillate"] = bool(status.get("oscillate", False))

        if "speed" in status and status.get("speed") is not None:
            speed_range = (
                FAN_DEVICE.get("config", {}).get(device_model, {}).get("speed_range")
            )
            if speed_range:
                speed_value = float(status.get("speed", 0))
                fan_data["speed_percentage"] = int(
                    ranged_value_to_percentage(speed_range, speed_value)
                )

        return fan_data


# Use generic device data type
class DreoDataUpdateCoordinator(DataUpdateCoordinator[DreoDeviceData]):
    """Class to manage fetching Dreo data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: HsCloud,
        device_id: str,
        model: str | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.device_id = device_id
        self.device_model = model
        self.device_type = DEVICE_TYPE.get(model) if model else None
        # Initialize with generic device data type
        self.data = DreoGenericDeviceData(available=False, is_on=False)

    async def _async_update_data(self) -> DreoDeviceData:
        """Get device status from Dreo API and process it."""

        # Create base data structure
        base_data = DreoGenericDeviceData(available=False, is_on=False)

        try:
            # Get device status
            status = await self.hass.async_add_executor_job(
                self.client.get_status, self.device_id
            )

            if status is None:
                return base_data

            # Set common properties
            base_data["available"] = status.get("connected", False)
            base_data["is_on"] = status.get("power_switch", False)

            # Get device type and use factory to create appropriate data
            return DeviceDataFactory.create_data(self, base_data, status)
        except HsCloudException as error:
            raise UpdateFailed(f"Error communicating with Dreo API: {error}") from error
        except Exception as error:
            raise UpdateFailed(f"Unexpected error: {error}") from error
