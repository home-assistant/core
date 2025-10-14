"""Hanna Instruments data coordinator for Home Assistant.

This module provides the data coordinator for fetching and managing Hanna Instruments
sensor data.
"""

from datetime import timedelta
import logging
from typing import Any

from hanna_cloud import HannaCloudClient
from requests.exceptions import RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN


class HannaConfigEntry(ConfigEntry):
    """Config entry for Hanna integration with typed runtime data."""

    runtime_data: dict[str, "HannaDataCoordinator"] | None


_LOGGER = logging.getLogger(__name__)


class HannaDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for fetching Hanna sensor data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device: dict[str, Any],
        api_client: HannaCloudClient,
    ) -> None:
        """Initialize the Hanna data coordinator."""
        self.api_client = api_client
        self.readings = None
        self.device_data = device
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.device_identifier}",
            update_interval=timedelta(seconds=30),
        )

    @property
    def device_identifier(self) -> str:
        """Return the device identifier."""
        return self.device_data["DID"]

    def get_alerts(self, alert_types: str) -> list[str]:
        """Get all alerts from the sensor data."""
        alerts = []
        if alert_types == "alarms":
            alerts.extend(self.api_client.alarms)
        if alert_types == "errors":
            alerts.extend(self.api_client.errors)
        if alert_types == "warnings":
            alerts.extend(self.api_client.warnings)
        return alerts

    def get_parameters(self) -> list[dict[str, Any]]:
        """Get all parameters from the sensor data."""
        return self.api_client.parameters

    def get_parameter_value(self, key: str) -> Any:
        """Get the value for a specific parameter."""
        for parameter in self.get_parameters():
            if parameter["name"] == key:
                return parameter["value"]
        return None

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest sensor data from the Hanna API."""
        try:
            readings = await self.hass.async_add_executor_job(
                self.api_client.get_last_device_reading, self.device_identifier
            )
            self.readings = readings
        except RequestException as e:
            raise UpdateFailed(f"Error communicating with Hanna API: {e}") from e
        except (KeyError, IndexError) as e:
            raise UpdateFailed(f"Error parsing Hanna API response: {e}") from e
        return readings
