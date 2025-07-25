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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class HannaDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for fetching Hanna sensor data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device: dict,
    ) -> None:
        """Initialize the Hanna data coordinator."""
        self.api_client = HannaCloudClient()
        self.readings = None
        self.device_data = device
        self._email = config_entry.data["email"]
        self._password = config_entry.data["password"]
        super().__init__(
            hass,
            _LOGGER,
            name=f"hanna_{self.device_identifier}",
            update_interval=timedelta(seconds=30),
        )
        self._authenticated = False

    async def ensure_authenticated(self) -> None:
        """Ensure the client is authenticated with the Hanna API."""
        if not self._authenticated:
            await self.hass.async_add_executor_job(
                self.api_client.authenticate, self._email, self._password
            )
            self._authenticated = True

    @property
    def device_identifier(self) -> str:
        """Return the device identifier."""
        return self.device_data["DID"]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for Home Assistant."""
        return DeviceInfo(
            identifiers={("hanna", self.device_identifier)},
            manufacturer=self.device_data.get("manufacturer"),
            model=self.device_data.get("DM"),
            name=f"{self.device_identifier} {self.device_data.get('name')}",
            serial_number=self.device_data.get("serial_number"),
            sw_version=self.device_data.get("sw_version"),
        )

    def get_all_alarms(self) -> list[str]:
        """Get all alarms from the sensor data."""
        return (
            self.api_client.alarms + self.api_client.errors + self.api_client.warnings
        )

    def get_parameters(self) -> list[dict[str, Any]]:
        """Get all parameters from the sensor data."""
        return self.api_client.parameters

    def get_parameter_value(self, key: str) -> Any:
        """Get the value for a specific parameter."""
        for parameter in self.get_parameters():
            if parameter["name"] == key:
                return parameter["value"]
        return None

    async def _async_update_data(self):
        """Fetch latest sensor data from the Hanna API."""
        try:
            await self.ensure_authenticated()
            readings = await self.hass.async_add_executor_job(
                self.api_client.get_last_device_reading, self.device_identifier
            )
            self.readings = readings
        except RequestException as e:
            raise UpdateFailed(f"Error communicating with Hanna API: {e}") from e
        except (KeyError, IndexError) as e:
            raise UpdateFailed(f"Error parsing Hanna API response: {e}") from e
        except Exception as e:
            _LOGGER.error("Unexpected error while fetching Hanna data: %s", e)
            raise UpdateFailed(f"Unexpected error: {e}") from e
