"""Hanna Instruments data coordinator for Home Assistant.

This module provides the data coordinator for fetching and managing Hanna Instruments
sensor data.
"""

from datetime import datetime, timedelta
import logging
from typing import Any

from hanna_cloud import HannaCloudClient
from requests.exceptions import RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class HannaMainCoordinator(DataUpdateCoordinator):
    """Main coordinator for Hanna Instruments authentication and device management."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the main Hanna coordinator."""
        self.api_client = HannaCloudClient()
        self._devices: dict[str, dict] = {}
        update_interval = timedelta(minutes=config_entry.data.get("update_interval", 1))
        super().__init__(
            hass,
            _LOGGER,
            name="hanna_main",
            update_interval=update_interval,
        )

    async def async_authenticate(self, email: str, password: str, code: str) -> None:
        """Authenticate with the Hanna API."""
        await self.hass.async_add_executor_job(
            self.api_client.authenticate, email, password, code
        )

    async def async_get_devices(self) -> list[dict]:
        """Get all devices associated with the account."""
        devices = await self.hass.async_add_executor_job(self.api_client.get_devices)
        self._devices = {device.get("DID"): device for device in devices}
        return devices

    def get_device(self, device_id: str) -> dict:
        """Get a specific device by ID."""
        return self._devices[device_id]

    async def _async_update_data(self):
        """Update the list of devices."""
        try:
            await self.async_get_devices()
        except Exception as e:
            _LOGGER.error("Error updating devices: %s", e)
            raise UpdateFailed(f"Error updating devices: {e}") from e
        else:
            return self._devices


class HannaDataCoordinator(DataUpdateCoordinator):
    """Coordinator for fetching Hanna sensor data."""

    def __init__(
        self,
        hass: HomeAssistant,
        main_coordinator: HannaMainCoordinator,
        device: dict,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the Hanna data coordinator."""
        self.main_coordinator = main_coordinator
        self._device_data = device
        self._readings = None
        update_interval = timedelta(minutes=config_entry.data.get("update_interval", 1))
        super().__init__(
            hass,
            _LOGGER,
            name=f"hanna_{self.device_identifier}",
            update_interval=update_interval,
        )

    @property
    def api_client(self) -> HannaCloudClient:
        """Return the API client from the main coordinator."""
        return self.main_coordinator.api_client

    @property
    def device_identifier(self) -> str:
        """Return the device identifier."""
        return self._device_data["DID"]

    @property
    def device_data(self) -> dict:
        """Return the device data."""
        return self._device_data

    @property
    def readings(self) -> dict:
        """Return the readings."""
        return self._readings or {}

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for Home Assistant."""
        sy = self.device_data.get("reportedSettings", {}).get("SY")
        return DeviceInfo(
            identifiers={("hanna", self.device_identifier)},
            manufacturer="Hanna Instruments",
            model=self.device_data.get("DM"),
            name=f"{self.device_identifier} {self.device_data.get('DINFO', {}).get('deviceName')}",
            serial_number=sy.split(",")[4],
            sw_version="".join(sy.split(",")[2:4]).replace("&#47;", "/"),
        )

    def get_last_update_time(self) -> str:
        """Get the formatted last update time from sensor data."""
        format_string = "%Y-%m-%d %H:%M:%SZ"
        last_update_ts = int(self.get_messages_value("receivedAtUTCs"))
        last_update_dt = datetime.fromtimestamp(last_update_ts)
        return last_update_dt.strftime(format_string)

    def get_messages(self) -> dict[str, Any]:
        """Get the messages from the sensor data."""
        return self.get_readings().get("messages", {})

    def get_messages_value(self, key: str) -> Any:
        """Get the value for a specific key in the messages."""
        return self.get_messages().get(key)

    def get_glp(self) -> dict[str, Any]:
        """Get the glp from the sensor data."""
        return self.get_messages_value("glp")

    def get_glp_value(self, key: str) -> Any:
        """Get the value for a specific key in the glp."""
        return self.get_glp().get(key)

    def get_parameters(self) -> list[dict[str, Any]]:
        """Get all parameters from the sensor data."""
        return self.get_messages_value("parameters") or []

    def get_parameter_value(self, key: str) -> Any:
        """Get the value for a specific parameter."""
        for parameter in self.get_parameters():
            if parameter["name"] == key:
                return parameter["value"]
        return None

    def get_readings(self) -> dict[str, Any]:
        """Get the raw readings from the device."""
        return self._readings or {}

    async def _async_update_data(self):
        """Fetch latest sensor data from the Hanna API."""
        try:
            readings = await self.hass.async_add_executor_job(
                self.api_client.get_last_device_reading, self.device_identifier
            )
            self._readings = readings[0]
        except RequestException as e:
            raise UpdateFailed(f"Error communicating with Hanna API: {e}") from e
        except (KeyError, IndexError) as e:
            raise UpdateFailed(f"Error parsing Hanna API response: {e}") from e
        except Exception as e:
            _LOGGER.error("Unexpected error while fetching Hanna data: %s", e)
            raise UpdateFailed(f"Unexpected error: {e}") from e
