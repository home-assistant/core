"""MQTT-backed selects for Victron Remote Monitoring."""

from __future__ import annotations

from typing import Any

from victron_mqtt import (
    Device as VictronDevice,
    Metric as VictronMetric,
    MetricKind,
    WritableMetric as VictronWritableMetric,
)

from homeassistant.components.select import SelectEntity
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
    """Set up MQTT select entities from a config entry."""
    coordinator = entry.runtime_data
    mqtt_hub = coordinator.mqtt_hub

    def on_new_metric(
        device: VictronDevice,
        metric: VictronMetric,
        device_info: DeviceInfo,
        site_id: int,
    ) -> None:
        assert isinstance(metric, VictronWritableMetric)
        async_add_entities([VRMMqttSelect(device, metric, device_info, site_id)])

    mqtt_hub.register_new_metric_callback(MetricKind.SELECT, on_new_metric)


class VRMMqttSelect(VRMMqttBaseEntity, SelectEntity):
    """Select entity backed by Victron MQTT metrics."""

    def __init__(
        self,
        device: VictronDevice,
        metric: VictronWritableMetric,
        device_info: DeviceInfo,
        site_id: int,
    ) -> None:
        """Initialize the select entity."""
        assert metric.enum_values is not None
        self._attr_options = metric.enum_values
        self._attr_current_option = self._map_value_to_option(metric.value)
        super().__init__(device, metric, device_info, site_id)

    @callback
    def _on_update_task(self, value: Any) -> None:
        new_value = self._map_value_to_option(value)
        if self._attr_current_option == new_value:
            return
        self._attr_current_option = new_value
        self.async_write_ha_state()

    def select_option(self, option: str) -> None:
        """Select a new option."""
        assert isinstance(self._metric, VictronWritableMetric)
        assert self._metric.enum_values is not None
        if option not in self._metric.enum_values:
            return
        self._metric.set(option)

    @staticmethod
    def _map_value_to_option(value: Any) -> str:
        return str(value)
