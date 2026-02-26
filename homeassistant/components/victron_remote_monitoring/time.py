"""MQTT-backed time entities for Victron Remote Monitoring."""

from __future__ import annotations

from datetime import time
from typing import Any

from victron_mqtt import (
    Device as VictronDevice,
    Metric as VictronMetric,
    MetricKind,
    WritableMetric as VictronWritableMetric,
)

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import VictronRemoteMonitoringConfigEntry
from .entity import VRMMqttBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VictronRemoteMonitoringConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MQTT time entities from a config entry."""
    coordinator = entry.runtime_data
    mqtt_hub = coordinator.mqtt_hub

    def on_new_metric(
        device: VictronDevice,
        metric: VictronMetric,
        device_info: DeviceInfo,
        site_id: int,
    ) -> None:
        assert isinstance(metric, VictronWritableMetric)
        async_add_entities([VRMMqttTime(device, metric, device_info, site_id)])

    mqtt_hub.register_new_metric_callback(MetricKind.TIME, on_new_metric)


class VRMMqttTime(VRMMqttBaseEntity, TimeEntity):
    """Time entity backed by Victron MQTT metrics."""

    @staticmethod
    def _to_time(value: int | None) -> time | None:
        if value is None:
            return None
        total_minutes = int(value)
        return time(hour=total_minutes // 60, minute=total_minutes % 60)

    @staticmethod
    def _to_minutes(value: time) -> int:
        return value.hour * 60 + value.minute

    def __init__(
        self,
        device: VictronDevice,
        metric: VictronWritableMetric,
        device_info: DeviceInfo,
        site_id: int,
    ) -> None:
        """Initialize the time entity."""
        self._attr_native_value = self._to_time(metric.value)
        super().__init__(device, metric, device_info, site_id)

    @callback
    def _on_update_task(self, value: Any) -> None:
        new_time = self._to_time(value)
        if self._attr_native_value == new_time:
            return
        self._attr_native_value = new_time
        self.async_write_ha_state()

    def set_value(self, value: time) -> None:
        """Set a new time value."""
        assert isinstance(self._metric, VictronWritableMetric)
        self._metric.set(self._to_minutes(value))
