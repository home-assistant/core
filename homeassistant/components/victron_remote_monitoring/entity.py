"""Shared MQTT entity helpers for Victron Remote Monitoring."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from victron_mqtt import (
    Device as VictronDevice,
    Metric as VictronMetric,
    MetricNature,
    MetricType,
)

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity


class VRMMqttBaseEntity(Entity):
    """Base class for MQTT-backed entities."""

    def __init__(
        self,
        device: VictronDevice,
        metric: VictronMetric,
        device_info: DeviceInfo,
        site_id: int,
    ) -> None:
        """Initialize the MQTT entity."""
        self._device = device
        self._metric = metric
        self._attr_unique_id = f"{site_id}_{metric.unique_id}"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True
        self._attr_name = self._build_name(metric)
        self._attr_suggested_display_precision = metric.precision
        self._attr_native_unit_of_measurement = self._map_unit(metric)
        self._attr_device_class = self._map_device_class(metric)
        self._attr_state_class = self._map_state_class(metric)
        self._attr_should_poll = False

    @staticmethod
    def _build_name(metric: VictronMetric) -> str:
        name = getattr(metric, "name", None)
        return name or metric.short_id

    @staticmethod
    def _map_device_class(
        metric: VictronMetric,
    ) -> SensorDeviceClass | None:
        match metric.metric_type:
            case MetricType.POWER:
                return SensorDeviceClass.POWER
            case MetricType.APPARENT_POWER:
                return SensorDeviceClass.APPARENT_POWER
            case MetricType.ENERGY:
                return SensorDeviceClass.ENERGY
            case MetricType.VOLTAGE:
                return SensorDeviceClass.VOLTAGE
            case MetricType.CURRENT:
                return SensorDeviceClass.CURRENT
            case MetricType.FREQUENCY:
                return SensorDeviceClass.FREQUENCY
            case MetricType.ELECTRIC_STORAGE_PERCENTAGE:
                return SensorDeviceClass.BATTERY
            case MetricType.TEMPERATURE:
                return SensorDeviceClass.TEMPERATURE
            case MetricType.SPEED:
                return SensorDeviceClass.SPEED
            case MetricType.LIQUID_VOLUME:
                return SensorDeviceClass.VOLUME_STORAGE
            case MetricType.DURATION:
                return SensorDeviceClass.DURATION
            case MetricType.TIME:
                return None
            case _:
                return None

    @staticmethod
    def _map_state_class(
        metric: VictronMetric,
    ) -> SensorStateClass | str | None:
        if metric.metric_nature == MetricNature.CUMULATIVE:
            return SensorStateClass.TOTAL
        if metric.metric_nature == MetricNature.INSTANTANEOUS:
            return SensorStateClass.MEASUREMENT
        return None

    @staticmethod
    def _map_unit(metric: VictronMetric) -> str | None:
        if metric.unit_of_measurement == "s":
            return UnitOfTime.SECONDS
        if metric.unit_of_measurement == "min":
            return UnitOfTime.MINUTES
        if metric.unit_of_measurement == "h":
            return UnitOfTime.HOURS
        return metric.unit_of_measurement

    @abstractmethod
    def _on_update_task(self, value: Any) -> None:
        """Handle metric update in subclasses."""

    @callback
    def _on_update(self, metric: VictronMetric, value: Any) -> None:
        if self.hass is None:
            return
        self._on_update_task(value)

    async def async_added_to_hass(self) -> None:
        """Register update callback."""
        await super().async_added_to_hass()
        self._metric.on_update = self._on_update

    async def async_will_remove_from_hass(self) -> None:
        """Remove update callback."""
        self._metric.on_update = None
        await super().async_will_remove_from_hass()
