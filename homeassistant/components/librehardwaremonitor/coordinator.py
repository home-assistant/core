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
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


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
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

        host = config_entry.data[CONF_HOST]
        port = config_entry.data[CONF_PORT]
        self._api = LibreHardwareMonitorClient(host, port)
        device_entries = dr.async_entries_for_config_entry(
            registry=dr.async_get(self.hass), config_entry_id=config_entry.entry_id
        )
        self._previous_devices = {
            device.name for device in device_entries if device.name is not None
        }

    async def _async_update_data(self) -> LibreHardwareMonitorData:
        try:
            lhm_data = await self._api.get_data()
        except LibreHardwareMonitorConnectionError as err:
            raise UpdateFailed(
                "LibreHardwareMonitor connection failed, will retry"
            ) from err
        except LibreHardwareMonitorNoDevicesError as err:
            raise UpdateFailed("No sensor data available, will retry") from err

        await self._async_handle_changes_in_devices(lhm_data.main_device_names)

        return lhm_data

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

    async def _async_handle_changes_in_devices(
        self, detected_devices: list[str]
    ) -> None:
        """Handle device changes by deleting devices from / adding devices to Home Assistant."""
        if self._previous_devices == set(detected_devices) or self.config_entry is None:
            return

        if self.data is None:
            self._previous_devices = set(detected_devices)  # type: ignore[unreachable]
            return

        if orphaned_devices := list(self._previous_devices - set(detected_devices)):
            _LOGGER.info(
                "Devices no longer available, will be removed: %s", orphaned_devices
            )
            device_registry = dr.async_get(self.hass)
            for device_name in orphaned_devices:
                device = device_registry.async_get_device(
                    identifiers={(DOMAIN, device_name)}
                )
                if device:
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )

        if new_devices := list(set(detected_devices) - self._previous_devices):
            _LOGGER.info("New Device(s) added, reloading integration: %s", new_devices)
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

        self._previous_devices = set(detected_devices)
