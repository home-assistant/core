"""Coordinator for LibreHardwareMonitor integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from librehardwaremonitor_api import (
    LibreHardwareMonitorClient,
    LibreHardwareMonitorConnectionError,
    LibreHardwareMonitorNoDevicesError,
)
from librehardwaremonitor_api.model import LibreHardwareMonitorData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

RETRY_INTERVAL_WHEN_HOST_UNREACHABLE = 25


type LibreHardwareMonitorConfigEntry = ConfigEntry[LibreHardwareMonitorCoordinator]


class LibreHardwareMonitorCoordinator(DataUpdateCoordinator[LibreHardwareMonitorData]):
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
            lhm_data = await self._api.get_data()
            data_for_selected_devices = self._filter_for_selected_devices(lhm_data)
            self.update_interval = self._scan_interval
        except LibreHardwareMonitorConnectionError as err:
            self.update_interval = timedelta(
                seconds=RETRY_INTERVAL_WHEN_HOST_UNREACHABLE
            )
            raise UpdateFailed(
                "LibreHardwareMonitor connection failed, will retry"
            ) from err
        except LibreHardwareMonitorNoDevicesError as err:
            raise UpdateFailed(
                "No sensor data available for selected devices, will retry"
            ) from err

        return data_for_selected_devices

    def _filter_for_selected_devices(
        self, lhm_data: LibreHardwareMonitorData
    ) -> LibreHardwareMonitorData:
        sensor_data_for_selected_devices = {
            sensor_id: sensor_data
            for sensor_id, sensor_data in lhm_data.sensor_data.items()
            if sensor_data.device_name in self._selected_main_devices
        }

        if not sensor_data_for_selected_devices:
            raise LibreHardwareMonitorNoDevicesError

        return LibreHardwareMonitorData(sensor_data=sensor_data_for_selected_devices)

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
