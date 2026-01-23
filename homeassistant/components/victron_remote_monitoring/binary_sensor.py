"""MQTT-backed binary sensors for Victron Remote Monitoring."""

from __future__ import annotations

from typing import Any

from victron_mqtt import Device as VictronDevice, Metric as VictronMetric, MetricKind

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SWITCH_ON
from .coordinator import VictronRemoteMonitoringConfigEntry
from .entity import VRMMqttBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VictronRemoteMonitoringConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MQTT binary sensors from a config entry."""
    coordinator = entry.runtime_data
    mqtt_hub = coordinator.mqtt_hub

    def on_new_metric(
        device: VictronDevice,
        metric: VictronMetric,
        device_info: DeviceInfo,
        site_id: int,
    ) -> None:
        async_add_entities([VRMMqttBinarySensor(device, metric, device_info, site_id)])

    mqtt_hub.register_new_metric_callback(MetricKind.BINARY_SENSOR, on_new_metric)


class VRMMqttBinarySensor(VRMMqttBaseEntity, BinarySensorEntity):
    """Binary sensor backed by Victron MQTT metrics."""

    def __init__(
        self,
        device: VictronDevice,
        metric: VictronMetric,
        device_info: DeviceInfo,
        site_id: int,
    ) -> None:
        """Initialize the binary sensor."""
        self._attr_is_on = self._is_on(metric.value)
        super().__init__(device, metric, device_info, site_id)

    @staticmethod
    def _is_on(value: Any) -> bool:
        return str(value) == SWITCH_ON

    @callback
    def _on_update_task(self, value: Any) -> None:
        new_state = self._is_on(value)
        if self._attr_is_on == new_state:
            return
        self._attr_is_on = new_state
        self.async_write_ha_state()
