"""Support for tracking MySensors devices."""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import setup_mysensors_platform
from .const import MYSENSORS_DISCOVERY, DiscoveryInfo
from .device import MySensorsEntity
from .helpers import on_unload


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up this platform for a specific ConfigEntry(==Gateway)."""

    @callback
    def async_discover(discovery_info: DiscoveryInfo) -> None:
        """Discover and add a MySensors device tracker."""
        setup_mysensors_platform(
            hass,
            Platform.DEVICE_TRACKER,
            discovery_info,
            MySensorsDeviceTracker,
            async_add_entities=async_add_entities,
        )

    on_unload(
        hass,
        config_entry.entry_id,
        async_dispatcher_connect(
            hass,
            MYSENSORS_DISCOVERY.format(config_entry.entry_id, Platform.DEVICE_TRACKER),
            async_discover,
        ),
    )


class MySensorsDeviceTracker(MySensorsEntity, TrackerEntity):
    """Represent a MySensors device tracker."""

    _latitude: float | None = None
    _longitude: float | None = None

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self._latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self._longitude

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the device."""
        return SourceType.GPS

    @callback
    def _async_update(self) -> None:
        """Update the controller with the latest value from a device."""
        super()._async_update()
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        position: str = child.values[self.value_type]
        latitude, longitude, _ = position.split(",")
        self._latitude = float(latitude)
        self._longitude = float(longitude)
