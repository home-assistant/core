"""MQTT-backed switches for Victron Remote Monitoring."""

from __future__ import annotations

from typing import Any

from victron_mqtt import (
    Device as VictronDevice,
    Metric as VictronMetric,
    MetricKind,
    WritableMetric as VictronWritableMetric,
)

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SWITCH_OFF, SWITCH_ON
from .coordinator import VictronRemoteMonitoringConfigEntry
from .entity import VRMMqttBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VictronRemoteMonitoringConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MQTT switches from a config entry."""
    coordinator = entry.runtime_data
    mqtt_hub = coordinator.mqtt_hub

    def on_new_metric(
        device: VictronDevice,
        metric: VictronMetric,
        device_info: DeviceInfo,
        site_id: int,
    ) -> None:
        assert isinstance(metric, VictronWritableMetric)
        async_add_entities([VRMMqttSwitch(device, metric, device_info, site_id)])

    mqtt_hub.register_new_metric_callback(MetricKind.SWITCH, on_new_metric)


class VRMMqttSwitch(VRMMqttBaseEntity, SwitchEntity):
    """Switch backed by Victron MQTT metrics."""

    def __init__(
        self,
        device: VictronDevice,
        metric: VictronWritableMetric,
        device_info: DeviceInfo,
        site_id: int,
    ) -> None:
        """Initialize the switch."""
        self._attr_is_on = str(metric.value) == SWITCH_ON
        super().__init__(device, metric, device_info, site_id)

    @callback
    def _on_update_task(self, value: Any) -> None:
        new_state = str(value) == SWITCH_ON
        if self._attr_is_on == new_state:
            return
        self._attr_is_on = new_state
        self.async_write_ha_state()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        assert isinstance(self._metric, VictronWritableMetric)
        self._metric.set(SWITCH_ON)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        assert isinstance(self._metric, VictronWritableMetric)
        self._metric.set(SWITCH_OFF)
