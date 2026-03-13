"""The Airthings BLE integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from airthings_ble import (
    AirthingsBluetoothDeviceData,
    AirthingsConnectivityMode,
    AirthingsDevice,
)
from bleak.backends.device import BLEDevice
from bleak_retry_connector import close_stale_connections_by_address

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import (
    CONNECTIVITY_ISSUE_PREFIX,
    DEFAULT_SCAN_INTERVAL,
    DEVICE_MODEL,
    DEVICE_SPECIFIC_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

type AirthingsBLEConfigEntry = ConfigEntry[AirthingsBLEDataUpdateCoordinator]


class AirthingsBLEDataUpdateCoordinator(DataUpdateCoordinator[AirthingsDevice]):
    """Class to manage fetching Airthings BLE data."""

    ble_device: BLEDevice
    config_entry: AirthingsBLEConfigEntry

    def __init__(self, hass: HomeAssistant, entry: AirthingsBLEConfigEntry) -> None:
        """Initialize the coordinator."""
        self.airthings = AirthingsBluetoothDeviceData(
            _LOGGER, hass.config.units is METRIC_SYSTEM
        )

        device_model = entry.data.get(DEVICE_MODEL)
        interval = DEVICE_SPECIFIC_SCAN_INTERVAL.get(
            device_model, DEFAULT_SCAN_INTERVAL
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        address = self.config_entry.unique_id

        assert address is not None

        await close_stale_connections_by_address(address)

        ble_device = bluetooth.async_ble_device_from_address(self.hass, address)

        if not ble_device:
            raise ConfigEntryNotReady(
                f"Could not find Airthings device with address {address}"
            )
        self.ble_device = ble_device

        if DEVICE_MODEL not in self.config_entry.data:
            _LOGGER.debug("Fetching device info for migration")
            try:
                data = await self.airthings.update_device(self.ble_device)
            except Exception as err:
                raise UpdateFailed(
                    f"Unable to fetch data for migration: {err}"
                ) from err

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, DEVICE_MODEL: data.model.value},
            )
            self.update_interval = timedelta(
                seconds=DEVICE_SPECIFIC_SCAN_INTERVAL.get(
                    data.model.value, DEFAULT_SCAN_INTERVAL
                )
            )

    async def _async_update_data(self) -> AirthingsDevice:
        """Get data from Airthings BLE."""
        try:
            data = await self.airthings.update_device(self.ble_device)
        except Exception as err:
            raise UpdateFailed(f"Unable to fetch data: {err}") from err

        self._check_connectivity_mode_issue(data)
        return data

    @callback
    def _check_connectivity_mode_issue(self, data: AirthingsDevice) -> None:
        """Create or remove connectivity mode issue based on device data."""
        connectivity_mode = data.sensors.get("connectivity_mode")
        if connectivity_mode is None:
            return

        issue_id = f"{CONNECTIVITY_ISSUE_PREFIX}{data.address}"
        serial_number = f"{data.model.value}{data.identifier}"

        if connectivity_mode == AirthingsConnectivityMode.SMARTLINK.value:
            ir.async_create_issue(
                hass=self.hass,
                domain=DOMAIN,
                issue_id=issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="smartlink_detected",
                translation_placeholders={
                    "device_name": data.friendly_name(),
                    "serial_number": serial_number,
                },
            )
        elif connectivity_mode == AirthingsConnectivityMode.NOT_CONFIGURED.value:
            ir.async_create_issue(
                hass=self.hass,
                domain=DOMAIN,
                issue_id=issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="not_configured",
                translation_placeholders={
                    "device_name": data.friendly_name(),
                    "serial_number": serial_number,
                },
            )
        else:
            ir.async_delete_issue(
                hass=self.hass,
                domain=DOMAIN,
                issue_id=issue_id,
            )
