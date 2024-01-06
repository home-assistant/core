"""Tracking for bluetooth low energy devices."""
from __future__ import annotations

from collections.abc import Mapping
import logging

from homeassistant.components import bluetooth
from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import BaseTrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import BasePrivateDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load Device Tracker entities for a config entry."""
    async_add_entities([BasePrivateDeviceTracker(config_entry)])


class BasePrivateDeviceTracker(BasePrivateDeviceEntity, BaseTrackerEntity):
    """A trackable Private Bluetooth Device."""

    _attr_should_poll = False
    _attr_has_entity_name = True
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
    def state(self) -> str:
        """Return the state of the device."""
        return STATE_HOME if self._last_info else STATE_NOT_HOME

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.BLUETOOTH_LE

    @property
    def icon(self) -> str:
        """Return device icon."""
        return "mdi:bluetooth-connect" if self._last_info else "mdi:bluetooth-off"
