"""MQTT-backed buttons for Victron Remote Monitoring."""

from __future__ import annotations

from typing import Any

from victron_mqtt import (
    Device as VictronDevice,
    Metric as VictronMetric,
    MetricKind,
    WritableMetric as VictronWritableMetric,
)

from homeassistant.components.button import ButtonEntity
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
    """Set up MQTT button entities from a config entry."""
    coordinator = entry.runtime_data
    mqtt_hub = coordinator.mqtt_hub

    def on_new_metric(
        device: VictronDevice,
        metric: VictronMetric,
        device_info: DeviceInfo,
        site_id: int,
    ) -> None:
        assert isinstance(metric, VictronWritableMetric)
        async_add_entities([VRMMqttButton(device, metric, device_info, site_id)])

    mqtt_hub.register_new_metric_callback(MetricKind.BUTTON, on_new_metric)


class VRMMqttButton(VRMMqttBaseEntity, ButtonEntity):
    """Button entity backed by Victron MQTT metrics."""

    def __init__(
        self,
        device: VictronDevice,
        metric: VictronWritableMetric,
        device_info: DeviceInfo,
        site_id: int,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(device, metric, device_info, site_id)

    @callback
    def _on_update_task(self, value: Any) -> None:
        """Handle updates from the metric."""

    def press(self) -> None:
        """Press the button."""
        assert isinstance(self._metric, VictronWritableMetric)
        self._metric.set(SWITCH_ON)
