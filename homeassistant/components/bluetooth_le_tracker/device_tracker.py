"""Support for tracking Bluetooth LE devices."""
from __future__ import annotations

import logging

from bleak.backends.device import BLEDevice

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import BaseTrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_ADDRESS, BLE_PREFIX, DOMAIN, SIGNAL_BLE_DEVICE_NEW
from .data import BLEScanner, signal_battery_update, signal_seen, signal_unavailable

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for Nmap Tracker component."""
    ble_scanner: BLEScanner = hass.data[DOMAIN]

    @callback
    def _async_device_new(ble_device: BLEDevice) -> None:
        """Signal a new device."""
        async_add_entities([BLETrackerEntity(ble_scanner, ble_device)])

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_BLE_DEVICE_NEW, _async_device_new)
    )


class BLETrackerEntity(BaseTrackerEntity):
    """An BLE Tracker entity."""

    _attr_should_poll = False

    def __init__(self, ble_scanner: BLEScanner, ble_device: BLEDevice) -> None:
        """Initialize an nmap tracker entity."""
        self._ble_scanner = ble_scanner
        self._ble_device = ble_device
        self._active = True
        self._battery_level: int | None = None

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the device."""
        return self._battery_level

    @property
    def state(self) -> str:
        """Return the state of the device."""
        return STATE_HOME if self._active else STATE_NOT_HOME

    @property
    def name(self) -> str:
        """Return device name."""
        return self._ble_device.name

    @property
    def unique_id(self) -> str:
        """Return device unique id."""
        return f"{BLE_PREFIX}{self._ble_device.address}"

    @property
    def source_type(self) -> SourceType:
        """Return tracker source type."""
        return SourceType.BLUETOOTH_LE

    @property
    def icon(self) -> str:
        """Return device icon."""
        return "mdi:bluetooth-connect" if self._active else "mdi:bluetooth-off"

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the device state attributes."""
        return {
            ATTR_ADDRESS: self._ble_device.address,
        }

    @callback
    def _async_battery_update(self, battery_level: int) -> None:
        """Handle battery update signal."""
        self._battery_level = battery_level
        self.async_write_ha_state()

    @callback
    def _async_seen(self, ble_device: BLEDevice) -> None:
        """Update state."""
        self._active = True
        self._ble_device = ble_device
        self.async_write_ha_state()

    @callback
    def _async_unavailable(self, ble_device: BLEDevice) -> None:
        """Update state."""
        self._active = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_seen(self._ble_device.address),
                self._async_seen,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_unavailable(self._ble_device.address),
                self._async_unavailable,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_battery_update(self._ble_device.address),
                self._async_battery_update,
            )
        )
