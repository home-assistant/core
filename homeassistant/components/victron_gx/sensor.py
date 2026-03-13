"""Support for Victron GX sensors."""

from typing import Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    Metric as VictronVenusMetric,
    MetricKind,
    MetricNature,
    MetricType,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import VictronBaseEntity
from .hub import VictronGxConfigEntry

PARALLEL_UPDATES = 0  # There is no I/O in the entity itself.

METRIC_TYPE_TO_DEVICE_CLASS: dict[MetricType, SensorDeviceClass] = {
    MetricType.POWER: SensorDeviceClass.POWER,
    MetricType.APPARENT_POWER: SensorDeviceClass.APPARENT_POWER,
    MetricType.ENERGY: SensorDeviceClass.ENERGY,
    MetricType.VOLTAGE: SensorDeviceClass.VOLTAGE,
    MetricType.CURRENT: SensorDeviceClass.CURRENT,
    MetricType.FREQUENCY: SensorDeviceClass.FREQUENCY,
    MetricType.ELECTRIC_STORAGE_PERCENTAGE: SensorDeviceClass.BATTERY,
    MetricType.TEMPERATURE: SensorDeviceClass.TEMPERATURE,
    MetricType.SPEED: SensorDeviceClass.SPEED,
    MetricType.LIQUID_VOLUME: SensorDeviceClass.VOLUME_STORAGE,
    MetricType.DURATION: SensorDeviceClass.DURATION,
}

METRIC_NATURE_TO_STATE_CLASS: dict[MetricNature, SensorStateClass] = {
    MetricNature.CUMULATIVE: SensorStateClass.TOTAL_INCREASING,
    MetricNature.INSTANTANEOUS: SensorStateClass.MEASUREMENT,
}

UNIT_MAPPING: dict[str, str] = {
    "s": UnitOfTime.SECONDS,
    "min": UnitOfTime.MINUTES,
    "h": UnitOfTime.HOURS,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VictronGxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Victron GX sensors from a config entry."""
    hub = config_entry.runtime_data

    def on_new_metric(
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
    ) -> None:
        """Handle new sensor metric discovery."""
        async_add_entities(
            [
                VictronSensor(
                    device,
                    metric,
                    device_info,
                )
            ]
        )

    hub.register_new_metric_callback(MetricKind.SENSOR, on_new_metric)


class VictronSensor(VictronBaseEntity, SensorEntity):
    """Implementation of a Victron GX sensor."""

    def __init__(
        self,
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device, metric, device_info)
        self._attr_device_class = METRIC_TYPE_TO_DEVICE_CLASS.get(metric.metric_type)
        self._attr_state_class = METRIC_NATURE_TO_STATE_CLASS.get(metric.metric_nature)
        unit = metric.unit_of_measurement
        self._attr_native_unit_of_measurement = (
            UNIT_MAPPING.get(unit, unit) if unit is not None else None
        )
        self._attr_native_value = metric.value

    @callback
    def _on_update_cb(self, value: Any) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
