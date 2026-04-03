"""Data update coordinator for Dreo devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from pydreo.client import DreoClient
from pydreo.exceptions import DreoException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.percentage import ranged_value_to_percentage

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)


@dataclass(slots=True)
class DreoFanDeviceData:
    """Data specific to Dreo fan devices."""

    is_on: bool = False
    mode: str | None = None
    oscillate: bool | None = None
    speed_percentage: int | None = None

    @staticmethod
    def process_fan_data(
        status: dict[str, Any], model_config: dict[str, Any]
    ) -> DreoFanDeviceData:
        """Process fan device specific data."""

        fan_data = DreoFanDeviceData(is_on=status.get("power_switch") is True)

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


class DreoDataUpdateCoordinator(DataUpdateCoordinator[DreoFanDeviceData]):
    """Class to manage fetching Dreo data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: DreoClient,
        device_id: str,
        model_config: dict[str, Any],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.device_id = device_id
        self.model_config = model_config

    async def _async_update_data(self) -> DreoFanDeviceData:
        """Get device status from Dreo API and process it."""

        try:
            status = await self.hass.async_add_executor_job(
                self.client.get_status, self.device_id
            )
        except DreoException as error:
            raise UpdateFailed(f"Error communicating with Dreo API: {error}") from error
        except Exception as error:
            raise UpdateFailed(f"Unexpected error: {error}") from error

        if status is None:
            raise UpdateFailed(f"No status available for device {self.device_id}")

        if status.get("connected") is not True:
            raise UpdateFailed(f"Device {self.device_id} is unavailable")

        return DreoFanDeviceData.process_fan_data(status, self.model_config)
