"""Coordinator for LibreHardwareMonitor integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from librehardwaremonitor_api import (
    LibreHardwareMonitorClient,
    LibreHardwareMonitorConnectionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

RETRY_INTERVAL_WHEN_HOST_UNREACHABLE = 25

LHM_CHILDREN = "Children"
LHM_DEVICE_TYPE = "ImageURL"
LHM_MIN = "Min"
LHM_MAX = "Max"
LHM_NAME = "Text"
LHM_SENSOR_ID = "SensorId"
LHM_TYPE = "Type"
LHM_VALUE = "Value"


class LibreHardwareMonitorCoordinator(DataUpdateCoordinator):
    """Class to manage fetching LibreHardwareMonitor data."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=timedelta(seconds=config_entry.data[CONF_SCAN_INTERVAL]),
        )

        host = config_entry.data[CONF_HOST]
        port = config_entry.data[CONF_PORT]
        self._scan_interval = timedelta(seconds=config_entry.data[CONF_SCAN_INTERVAL])
        self._selected_main_devices = config_entry.options[CONF_DEVICES]
        self._api = LibreHardwareMonitorClient(host, port)

    async def _async_update_data(self):
        try:
            lhm_data = await self._api.get_data_json()
            self.update_interval = self._scan_interval
        except LibreHardwareMonitorConnectionError as err:
            self.update_interval = timedelta(
                seconds=RETRY_INTERVAL_WHEN_HOST_UNREACHABLE
            )
            raise UpdateFailed(
                "LibreHardwareMonitor connection failed, will retry"
            ) from err

        return self._parse_all_sensors(lhm_data)

    async def _async_refresh(
        self,
        log_failures: bool = True,
        raise_on_auth_failed: bool = False,
        scheduled: bool = False,
        raise_on_entry_error: bool = False,
    ) -> None:
        # we don't expect the computer to be online 24/7 so we don't want to log a connection loss as an error
        await super()._async_refresh(
            False, raise_on_auth_failed, scheduled, raise_on_entry_error
        )

    def _parse_all_sensors(self, lhm_data) -> dict[str, LibreHardwareMonitorSensorData]:
        """Get data from all sensors across all devices."""
        sensors_data: dict[str, LibreHardwareMonitorSensorData] = {}

        for main_device in lhm_data[LHM_CHILDREN][0][LHM_CHILDREN]:
            device_name = main_device[LHM_NAME]

            if device_name not in self._selected_main_devices:
                continue

            device_type = self._parse_device_type(main_device)

            all_sensors_for_device = self._flatten_sensors(main_device)
            for sensor in all_sensors_for_device:
                sensor_id = "-".join(sensor[LHM_SENSOR_ID].split("/")[1:]).replace(
                    "%", ""
                )

                unit = None
                if " " in sensor[LHM_VALUE]:
                    unit = sensor[LHM_VALUE].split(" ")[1]

                sensor_data = LibreHardwareMonitorSensorData(
                    name=f"{sensor[LHM_NAME]} {sensor[LHM_TYPE]}",
                    value=sensor[LHM_VALUE].split(" ")[0],
                    min=sensor[LHM_MIN].split(" ")[0],
                    max=sensor[LHM_MAX].split(" ")[0],
                    unit=unit,
                    device_name=device_name,
                    device_type=device_type,
                    sensor_id=sensor_id,
                )
                sensors_data[sensor_id] = sensor_data

        return sensors_data

    def _parse_device_type(self, main_device):
        """Parse the device type from the image url property."""
        device_type = ""
        if "/" in main_device[LHM_DEVICE_TYPE]:
            device_type = main_device[LHM_DEVICE_TYPE].split("/")[1].split(".")[0]
        return device_type.upper() if device_type != "transparent" else "UNKNOWN"

    def _flatten_sensors(self, device):
        """Recursively find all sensors."""
        if not device[LHM_CHILDREN]:
            return [device]
        return [
            sensor
            for child in device[LHM_CHILDREN]
            for sensor in self._flatten_sensors(child)
        ]


@dataclass
class LibreHardwareMonitorSensorData:
    """Data class to hold all relevant sensor data."""

    name: str
    value: str
    min: str
    max: str
    unit: str | None
    device_name: str
    device_type: str
    sensor_id: str
