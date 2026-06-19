"""Tracking for bluetooth low energy devices."""

from collections.abc import Mapping
import logging

from homeassistant.components import bluetooth
from homeassistant.components.device_tracker import BaseScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import BasePrivateDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Load Device Tracker entities for a config entry."""
    async_add_entities([BasePrivateDeviceTracker(config_entry)])


class BasePrivateDeviceTracker(BasePrivateDeviceEntity, BaseScannerEntity):
    """A trackable Private Bluetooth Device."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_source_type: SourceType = SourceType.BLUETOOTH_LE
    _attr_translation_key = "device_tracker"
    _attr_name = None

    @property
    def extra_state_attributes(self) -> Mapping[str, str]:
        """Return extra state attributes for this device."""
        if last_info := self._last_info:
            return {
                "current_address": last_info.address,
                "source": last_info.source,
            }
        return {}

    @callback
    def _async_track_unavailable(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        self._last_info = None
        self.async_write_ha_state()

    @callback
    def _async_track_service_info(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        self._last_info = service_info
        self.async_write_ha_state()

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected."""
        return bool(self._last_info)
