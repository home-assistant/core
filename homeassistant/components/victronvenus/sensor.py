"""Support for Victron Venus sensors.

This module is light-weight and only registers the sensors with Home Assistant. The sensor class is implemented in the victronvenus_sensor module.
"""

from victronvenusclient import (
    Device as VictronVenusDevice,
    Hub as VictronVenusHub,
    Metric as VictronVenusMetric,
)
from victronvenusclient.constants import (
    PLACEHOLDER_PHASE,
    DeviceType,
    MetricNature,
    MetricType,
)

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ._victron_integration import VictronVenusConfigEntry
from .const import DOMAIN


class VictronSensor(SensorEntity):
    """Implementation of a Victron Venus sensor."""

    def __init__(
        self,
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor based on detauls in the metric."""
        self._device = device
        self._metric = metric
        self._metric.on_update = self._on_update
        self._registered_with_homeassistant = False
        self._device_info = device_info
        self._attr_native_unit_of_measurement = metric.unit_of_measurement
        self._attr_device_class = self._map_metric_to_device_class(metric)
        self._attr_state_class = self._map_metric_to_stateclass(metric)
        self._attr_unique_id = metric.unique_id
        self._attr_native_value = metric.value
        self._attr_should_poll = False
        self._attr_has_entity_name = True
        self._attr_suggested_display_precision = metric.precision
        translation_key = metric.generic_short_id
        translation_key = translation_key.replace(
            PLACEHOLDER_PHASE, "lx"
        )  # for translation key we do generic replacement
        self._attr_translation_key = translation_key
        if metric.phase is not None:
            self._attr_translation_placeholders = {"phase": metric.phase}

    def _on_update(self, metric: VictronVenusMetric):
        if self._registered_with_homeassistant:
            self._attr_native_value = metric.value
            self.async_write_ha_state()

    def mark_registered_with_homeassistant(self):
        """Mark the sensor as registered with Home Assistant, so that updates can be propagated."""
        self._registered_with_homeassistant = True

    def _map_metric_to_device_class(
        self, metric: VictronVenusMetric
    ) -> SensorDeviceClass | None:
        match metric.metric_type:
            case MetricType.TEMPERATURE:
                return SensorDeviceClass.TEMPERATURE
            case MetricType.POWER:
                if metric.unit_of_measurement == "VA":
                    return SensorDeviceClass.APPARENT_POWER
                return SensorDeviceClass.POWER
            case MetricType.ENERGY:
                return SensorDeviceClass.ENERGY
            case MetricType.VOLTAGE:
                return SensorDeviceClass.VOLTAGE
            case MetricType.CURRENT:
                return SensorDeviceClass.CURRENT
            case MetricType.FREQUENCY:
                return SensorDeviceClass.FREQUENCY
            case MetricType.PERCENTAGE:
                if metric.device_type == DeviceType.BATTERY:
                    return SensorDeviceClass.BATTERY
                return None
            case _:
                return None

    def _map_metric_to_stateclass(
        self, metric: VictronVenusMetric
    ) -> SensorStateClass | None:
        if metric.metric_nature == MetricNature.CUMULATIVE:
            return SensorStateClass.TOTAL_INCREASING
        if metric.metric_nature == MetricNature.INSTANTANEOUS:
            return SensorStateClass.MEASUREMENT

        return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about the sensor."""
        return self._device_info


def _map_device_info(device: VictronVenusDevice) -> DeviceInfo:
    info: DeviceInfo = {}
    info["identifiers"] = {(DOMAIN, device.unique_id)}
    info["manufacturer"] = device.manufacturer
    info["name"] = device.name
    info["model"] = device.model
    info["serial_number"] = device.serial_number

    return info


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VictronVenusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Victron Venus sensors from a config entry."""

    hub: VictronVenusHub = config_entry.runtime_data

    devices: VictronVenusDevice = hub.devices

    for device in devices:
        info = _map_device_info(device)
        metrics = device.metrics
        for metric in metrics:
            sensor = VictronSensor(device, metric, info)
            async_add_entities([sensor])
            sensor.mark_registered_with_homeassistant()
