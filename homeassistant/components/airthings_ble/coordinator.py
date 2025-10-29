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
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

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
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
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

    async def _async_update_data(self) -> AirthingsDevice:
        """Get data from Airthings BLE."""
        try:
            data = await self.airthings.update_device(self.ble_device)
        except Exception as err:
            raise UpdateFailed(f"Unable to fetch data: {err}") from err

        try:
            if connectivity_mode := data.sensors.get("connectivity_mode"):
                issue_id = f"smartlink_detected_{data.address}"

                # Find sensors with connectivity mode set to smartlink (hub)
                # or not configured
                if connectivity_mode in [
                    AirthingsConnectivityMode.SMARTLINK.value,
                    AirthingsConnectivityMode.NOT_CONFIGURED.value,
                ]:
                    ir.async_create_issue(
                        hass=self.hass,
                        domain=DOMAIN,
                        issue_id=issue_id,
                        is_fixable=False,
                        severity=ir.IssueSeverity.WARNING,
                        translation_key="smartlink_detected",
                        translation_placeholders={"device_name": data.friendly_name()},
                    )
                elif connectivity_mode == AirthingsConnectivityMode.BLE.value:
                    ir.async_delete_issue(
                        hass=self.hass,
                        domain=DOMAIN,
                        issue_id=issue_id,
                    )
        except Exception:
            _LOGGER.exception("Error checking connectivity mode for issues")
        return data
