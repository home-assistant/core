"""Coordinator for LibreHardwareMonitor integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from librehardwaremonitor_api import (
    LibreHardwareMonitorClient,
    LibreHardwareMonitorConnectionError,
    LibreHardwareMonitorNoDevicesError,
)
from librehardwaremonitor_api.model import (
    DeviceId,
    DeviceName,
    LibreHardwareMonitorData,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


type LibreHardwareMonitorConfigEntry = ConfigEntry[LibreHardwareMonitorCoordinator]


class LibreHardwareMonitorCoordinator(DataUpdateCoordinator[LibreHardwareMonitorData]):
    """Class to manage fetching LibreHardwareMonitor data."""

    config_entry: LibreHardwareMonitorConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: LibreHardwareMonitorConfigEntry
    ) -> None:
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
        device_entries: list[DeviceEntry] = dr.async_entries_for_config_entry(
            registry=dr.async_get(self.hass), config_entry_id=config_entry.entry_id
        )
        self._previous_devices: dict[DeviceId, DeviceName] = {
            DeviceId(next(iter(device.identifiers))[1]): DeviceName(device.name)
            for device in device_entries
            if device.identifiers and device.name
        }

    async def _async_update_data(self) -> LibreHardwareMonitorData:
        try:
            lhm_data = await self._api.get_data()
        except LibreHardwareMonitorConnectionError as err:
            raise UpdateFailed(
                "LibreHardwareMonitor connection failed, will retry", retry_after=30
            ) from err
        except LibreHardwareMonitorNoDevicesError as err:
            raise UpdateFailed("No sensor data available, will retry") from err

        await self._async_handle_changes_in_devices(
            dict(lhm_data.main_device_ids_and_names)
        )

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
        self, detected_devices: dict[DeviceId, DeviceName]
    ) -> None:
        """Handle device changes by deleting devices from / adding devices to Home Assistant."""
        detected_devices = {
            DeviceId(f"{self.config_entry.entry_id}_{detected_id}"): device_name
            for detected_id, device_name in detected_devices.items()
        }

        previous_device_ids = set(self._previous_devices.keys())
        detected_device_ids = set(detected_devices.keys())

        _LOGGER.debug("Previous device_ids: %s", previous_device_ids)
        _LOGGER.debug("Detected device_ids: %s", detected_device_ids)

        if previous_device_ids == detected_device_ids:
            return

        if orphaned_devices := previous_device_ids - detected_device_ids:
            _LOGGER.warning(
                "Device(s) no longer available, will be removed: %s",
                [self._previous_devices[device_id] for device_id in orphaned_devices],
            )
            device_registry = dr.async_get(self.hass)
            for device_id in orphaned_devices:
                if device := device_registry.async_get_device(
                    identifiers={(DOMAIN, device_id)}
                ):
                    _LOGGER.debug(
                        "Removing device: %s", self._previous_devices[device_id]
                    )
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )

        if self.data is None:
            # initial update during integration startup
            self._previous_devices = detected_devices  # type: ignore[unreachable]
            return

        if new_devices := detected_device_ids - previous_device_ids:
            _LOGGER.warning(
                "New Device(s) detected, reload integration to add them to Home Assistant: %s",
                [detected_devices[DeviceId(device_id)] for device_id in new_devices],
            )

        self._previous_devices = detected_devices
