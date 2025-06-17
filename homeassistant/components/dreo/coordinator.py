"""Data update coordinator for Dreo devices."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from hscloud.const import DEVICE_TYPE, FAN_DEVICE
from hscloud.hscloud import HsCloud
from hscloud.hscloudexception import HsCloudException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.percentage import ranged_value_to_percentage

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


class DreoGenericDeviceData:
    """Base data for all Dreo devices."""

    available: bool = False
    is_on: bool = False

    def __init__(self, available: bool = False, is_on: bool = False) -> None:
        """Initialize generic device data."""
        self.available = available
        self.is_on = is_on


class DreoFanDeviceData(DreoGenericDeviceData):
    """Data specific to Dreo fan devices."""

    mode: str | None = None
    oscillate: bool | None = None
    speed_percentage: int | None = None

    def __init__(
        self,
        available: bool = False,
        is_on: bool = False,
        mode: str | None = None,
        oscillate: bool | None = None,
        speed_percentage: int | None = None,
    ) -> None:
        """Initialize fan device data."""
        super().__init__(available, is_on)
        self.mode = mode
        self.oscillate = oscillate
        self.speed_percentage = speed_percentage

    @staticmethod
    def process_fan_data(
        device_model: str, status: dict[str, Any]
    ) -> DreoFanDeviceData:
        """Process fan device specific data."""

        fan_data = DreoFanDeviceData(
            available=status.get("connected", False),
            is_on=status.get("power_switch", False),
        )

        if (mode := status.get("mode")) is not None:
            fan_data.mode = str(mode)

        if (oscillate := status.get("oscillate")) is not None:
            fan_data.oscillate = bool(oscillate)

        if (speed := status.get("speed")) is not None:
            speed_range = (
                FAN_DEVICE.get("config", {}).get(device_model, {}).get("speed_range")
            )
            if speed_range:
                fan_data.speed_percentage = int(
                    ranged_value_to_percentage(speed_range, float(speed))
                )

        return fan_data


DreoDeviceData = DreoFanDeviceData


class DreoDataUpdateCoordinator(DataUpdateCoordinator[DreoDeviceData | None]):
    """Class to manage fetching Dreo data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: HsCloud,
        device_id: str,
        model: str,
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

    def _create_device_data(self, status: dict[str, Any]) -> DreoDeviceData | None:
        """Create appropriate device data based on device type."""
        if self.device_type == FAN_DEVICE.get("type") and self.device_model:
            return DreoFanDeviceData.process_fan_data(self.device_model, status)

        _LOGGER.warning(
            "Unsupported device type: %s for model: %s - data will not be processed",
            self.device_type,
            self.device_model,
        )

        return None

    async def _async_update_data(self) -> DreoDeviceData | None:
        """Get device status from Dreo API and process it."""
        try:
            status = await self.hass.async_add_executor_job(
                self.client.get_status, self.device_id
            )

            if status is None:
                return None

            return self._create_device_data(status)
        except HsCloudException as error:
            raise UpdateFailed(f"Error communicating with Dreo API: {error}") from error
        except Exception as error:
            raise UpdateFailed(f"Unexpected error: {error}") from error
