"""MQTT-backed numbers for Victron Remote Monitoring."""

from __future__ import annotations

from typing import Any

from victron_mqtt import (
    Device as VictronDevice,
    Metric as VictronMetric,
    MetricKind,
    WritableMetric as VictronWritableMetric,
)

from homeassistant.components.number import NumberEntity
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
    """Set up MQTT number entities from a config entry."""
    coordinator = entry.runtime_data
    mqtt_hub = coordinator.mqtt_hub

    def on_new_metric(
        device: VictronDevice,
        metric: VictronMetric,
        device_info: DeviceInfo,
        site_id: int,
    ) -> None:
        assert isinstance(metric, VictronWritableMetric)
        async_add_entities([VRMMqttNumber(device, metric, device_info, site_id)])

    mqtt_hub.register_new_metric_callback(MetricKind.NUMBER, on_new_metric)


class VRMMqttNumber(VRMMqttBaseEntity, NumberEntity):
    """Number entity backed by Victron MQTT metrics."""

    def __init__(
        self,
        device: VictronDevice,
        metric: VictronWritableMetric,
        device_info: DeviceInfo,
        site_id: int,
    ) -> None:
        """Initialize the number entity."""
        self._attr_native_value = metric.value
        if isinstance(metric.min_value, int | float):
            self._attr_native_min_value = metric.min_value
        if isinstance(metric.max_value, int | float):
            self._attr_native_max_value = metric.max_value
        if isinstance(metric.step, int | float):
            self._attr_native_step = metric.step
        super().__init__(device, metric, device_info, site_id)

    @callback
    def _on_update_task(self, value: Any) -> None:
        if self._attr_native_value == value:
            return
        self._attr_native_value = value
        self.async_write_ha_state()

    def set_native_value(self, value: float) -> None:
        """Set a new value."""
        assert isinstance(self._metric, VictronWritableMetric)
        self._metric.set(value)
