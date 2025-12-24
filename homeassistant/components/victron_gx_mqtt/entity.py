"""Common code for Victron Venus integration."""

from abc import abstractmethod
import logging
from typing import Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    Metric as VictronVenusMetric,
    MetricKind,
    MetricNature,
    MetricType,
)

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import ENTITIES_CATEGORY_DIAGNOSTIC, ENTITIES_DISABLE_BY_DEFAULT

_LOGGER = logging.getLogger(__name__)


class VictronBaseEntity(Entity):
    """Implementation of a Victron Venus base entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the entity."""
        self._device = device
        self._metric = metric
        self._device_info = device_info
        self._attr_unique_id = metric.unique_id
        self._attr_suggested_display_precision = metric.precision
        self._attr_translation_key = metric.generic_short_id.replace("{", "").replace(
            "}", ""
        )  # same as in merge_topics.py
        self._attr_translation_placeholders = metric.key_values

        # Some attributes are relevant only for certain metric kinds
        if metric.metric_kind in [MetricKind.SENSOR, MetricKind.NUMBER]:
            self._attr_device_class = self._map_metric_to_device_class(metric)
            self._attr_state_class = self._map_metric_to_stateclass(metric)
            self._attr_native_unit_of_measurement = (
                self._map_metric_to_unit_of_measurement(metric)
            )

        self._attr_entity_category = (
            EntityCategory.DIAGNOSTIC
            if metric.generic_short_id in ENTITIES_CATEGORY_DIAGNOSTIC
            else None
        )
        self._attr_entity_registry_enabled_default = (
            metric.generic_short_id not in ENTITIES_DISABLE_BY_DEFAULT
        )

    @callback
    @abstractmethod
    def _on_update_task(self, value: Any) -> None:
        """Handle the metric update. Must be implemented by subclasses."""

    @callback
    def _on_update(self, metric: VictronVenusMetric, value: Any) -> None:
        self._on_update_task(value)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        # Now we can safely register for updates as the entity is fully registered with Home Assistant
        self._metric.on_update = self._on_update

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        # Remove our update callback by setting a no-op function
        self._metric.on_update = None
        await super().async_will_remove_from_hass()

    def _map_metric_to_device_class(
        self, metric: VictronVenusMetric
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
                return SensorDeviceClass.VOLUME
            case MetricType.DURATION:
                return SensorDeviceClass.DURATION
            case MetricType.TIME:
                # Sadly, there is no SensorDeviceClass for time
                return None
            case _:
                return None

    def _map_metric_to_stateclass(
        self, metric: VictronVenusMetric
    ) -> SensorStateClass | str | None:
        if metric.metric_nature == MetricNature.CUMULATIVE:
            return SensorStateClass.TOTAL
        if metric.metric_nature == MetricNature.INSTANTANEOUS:
            return SensorStateClass.MEASUREMENT

        return None

    def _map_metric_to_unit_of_measurement(
        self, metric: VictronVenusMetric
    ) -> str | None:
        if metric.unit_of_measurement == "s":
            return UnitOfTime.SECONDS
        if metric.unit_of_measurement == "min":
            return UnitOfTime.MINUTES
        if metric.unit_of_measurement == "h":
            return UnitOfTime.HOURS
        return metric.unit_of_measurement

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about the sensor."""
        return self._device_info
