"""Data update coordinator for Dreo devices."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from pydreo import DreoException
from pydreo.cloud.client import DreoClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    FIELD_CONNECTED,
)

if TYPE_CHECKING:
    from . import DreoConfigEntry

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

    if not isinstance(raw_speed_values, (list, tuple)) or len(raw_speed_values) < 2:
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


class DreoDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Dreo data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: DreoConfigEntry,
        client: DreoClient,
        device: dict[str, Any],
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
        self.device = device
        self.device_id = str(device["deviceSn"])
        self.model_config = model_config

    async def _async_update_data(self) -> dict[str, Any]:
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

        if status.get(FIELD_CONNECTED) is not True:
            raise UpdateFailed(f"Device {self.device_id} is unavailable")

        return status
