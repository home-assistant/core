"""Data update coordinator for Dreo devices."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any, NoReturn

from pydreo.client import DreoClient
from pydreo.exceptions import DreoException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.percentage import ranged_value_to_percentage

from .const import DOMAIN, FAN_DEVICE_TYPE

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=10)


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
        status: dict[str, Any], model_config: dict[str, Any]
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
            speed_range = model_config.get("speed_range")
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
        client: DreoClient,
        device_id: str,
        device_type: str,
        model_config: dict[str, Any],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.device_id = device_id
        self.device_type = device_type
        self.data_processor: (
            Callable[[dict[str, Any], dict[str, Any]], DreoDeviceData] | None
        )
        self.model_config = model_config

        if self.device_type == FAN_DEVICE_TYPE:
            self.data_processor = DreoFanDeviceData.process_fan_data
        else:
            _LOGGER.warning(
                "Unsupported device type: %s for model: %s - data will not be processed",
                self.device_type,
                self.device_id,
            )
            self.data_processor = None

    async def _async_update_data(self) -> DreoDeviceData | None:
        """Get device status from Dreo API and process it."""

        def _raise_no_status() -> NoReturn:
            """Raise UpdateFailed for no status available."""
            raise UpdateFailed(
                f"No status available for device {self.device_id} with type {self.device_type}"
            )

        def _raise_no_processor() -> NoReturn:
            """Raise UpdateFailed for no data processor available."""
            raise UpdateFailed(
                f"No data processor available for device {self.device_id} with type {self.device_type}"
            )

        try:
            status = await self.hass.async_add_executor_job(
                self.client.get_status, self.device_id
            )

            if status is None:
                _raise_no_status()

            if self.data_processor is None:
                _raise_no_processor()

            return self.data_processor(status, self.model_config)
        except DreoException as error:
            raise UpdateFailed(f"Error communicating with Dreo API: {error}") from error
        except Exception as error:
            raise UpdateFailed(f"Unexpected error: {error}") from error
