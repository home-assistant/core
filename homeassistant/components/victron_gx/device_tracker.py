"""Support for Victron GX device tracker."""

from __future__ import annotations

from typing import Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    GpsLocation,
    Metric as VictronVenusMetric,
    MetricKind,
)

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import VictronBaseEntity
from .hub import VictronGxConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VictronGxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Victron GX device trackers from a config entry."""
    hub = config_entry.runtime_data

    def on_new_metric(
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
        installation_id: str,
    ) -> None:
        """Handle new device tracker metric discovery."""
        async_add_entities(
            [VictronDeviceTracker(device, metric, device_info, installation_id)]
        )

    hub.register_new_metric_callback(MetricKind.DEVICE_TRACKER, on_new_metric)


class VictronDeviceTracker(VictronBaseEntity, TrackerEntity):
    """Implementation of a Victron GX device tracker."""

    _attr_source_type = SourceType.GPS

    def __init__(
        self,
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
        installation_id: str,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(device, metric, device_info, installation_id)
        if isinstance(metric.value, GpsLocation):
            self._attr_latitude = metric.value.latitude
            self._attr_longitude = metric.value.longitude

    @callback
    def _on_update_cb(self, value: Any) -> None:
        if isinstance(value, GpsLocation):
            self._attr_latitude = value.latitude
            self._attr_longitude = value.longitude
            self.async_write_ha_state()
