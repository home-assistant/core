"""Tracking for bluetooth low energy devices."""
from __future__ import annotations

from abc import abstractmethod
import binascii

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import async_get_coordinator, async_last_service_info


class BasePrivateDeviceEntity(Entity):
    """Base Private Bluetooth Entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Set up a new BleScanner entity."""
        irk = config_entry.data["irk"]

        if self.translation_key:
            self._attr_unique_id = f"{irk}_{self.translation_key}"
        else:
            self._attr_unique_id = irk

        self._attr_device_info = DeviceInfo(
            name=f"Private BLE Device {irk[:6]}",
            identifiers={(DOMAIN, irk)},
        )

        self._entry = config_entry
        self._irk = binascii.unhexlify(irk)
        self._last_info: bluetooth.BluetoothServiceInfoBleak | None = None

    async def async_added_to_hass(self) -> None:
        """Configure entity when it is added to Home Assistant."""
        coordinator = async_get_coordinator(self.hass)
        self.async_on_remove(
            coordinator.async_track_service_info(
                self._async_track_service_info, self._irk
            )
        )
        self.async_on_remove(
            coordinator.async_track_unavailable(
                self._async_track_unavailable, self._irk
            )
        )

        # There is a bug here - this doesn't set up availability tracking until an announcement is seen.
        if service_info := async_last_service_info(self.hass, self._irk):
            self._async_track_service_info(
                service_info, bluetooth.BluetoothChange.ADVERTISEMENT
            )

    @abstractmethod
    @callback
    def _async_track_unavailable(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        """Respond when the bluetooth device being tracked is no longer visible."""

    @abstractmethod
    @callback
    def _async_track_service_info(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Respond when the bluetooth device being tracked broadcasted updated information."""
