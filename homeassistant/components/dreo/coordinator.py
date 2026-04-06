"""Data update coordinator for Dreo devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from pydreo import DreoException
from pydreo.cloud.client import DreoClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.percentage import ordered_list_item_to_percentage

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)


def get_fan_model_config(model_config: dict[str, Any]) -> dict[str, Any]:
    """Return the fan-specific model config section."""
    if isinstance(model_config.get("fan_entity_config"), dict):
        return model_config["fan_entity_config"]

    return model_config


def get_speed_values(model_config: dict[str, Any]) -> list[int] | None:
    """Return normalized supported fan speed values."""
    raw_speed_values = get_fan_model_config(model_config).get("speed_range")

    if not isinstance(raw_speed_values, list | tuple) or len(raw_speed_values) < 2:
        return None

    try:
        speed_values = [int(value) for value in raw_speed_values]
    except TypeError, ValueError:
        return None

    if len(speed_values) == 2:
        low, high = speed_values
        if low < 1 or high < low:
            return None

        return list(range(low, high + 1))

    normalized_speed_values = sorted(set(speed_values))
    if normalized_speed_values[0] < 1:
        return None

    return normalized_speed_values


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
            try:
                speed_value = int(float(speed))
            except TypeError, ValueError:
                speed_value = None

            if speed_value == 0:
                fan_data.speed_percentage = 0
            elif (
                speed_value is not None
                and (speed_values := get_speed_values(model_config))
                and speed_value in speed_values
            ):
                fan_data.speed_percentage = ordered_list_item_to_percentage(
                    speed_values, speed_value
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
