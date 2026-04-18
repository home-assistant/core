"""Support for Victron GX sensors."""

from typing import Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    Metric as VictronVenusMetric,
    MetricKind,
    MetricNature,
    MetricType,
    VictronEnum,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
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
    MetricType.ENUM: SensorDeviceClass.ENUM,
}

METRIC_NATURE_TO_STATE_CLASS: dict[MetricNature, SensorStateClass] = {
    MetricNature.MEASUREMENT: SensorStateClass.MEASUREMENT,
    MetricNature.TOTAL: SensorStateClass.TOTAL,
    MetricNature.TOTAL_INCREASING: SensorStateClass.TOTAL_INCREASING,
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
        installation_id: str,
    ) -> None:
        """Handle new sensor metric discovery."""
        async_add_entities(
            [
                VictronSensor(
                    device,
                    metric,
                    device_info,
                    installation_id,
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
        installation_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device, metric, device_info, installation_id)
        self._attr_device_class = METRIC_TYPE_TO_DEVICE_CLASS.get(metric.metric_type)
        # Enum sensors must not have a state class
        if self._attr_device_class == SensorDeviceClass.ENUM:
            self._attr_options = metric.enum_values
        else:
            self._attr_state_class = METRIC_NATURE_TO_STATE_CLASS.get(
                metric.metric_nature
            )
        # Only set native_unit_of_measurement when a device_class is present.
        # Entities without a device_class get their display unit from
        # the translation files instead.
        if self._attr_device_class is not None:
            self._attr_native_unit_of_measurement = metric.unit_of_measurement
        self._attr_native_value = VictronSensor._normalize_value(metric.value)

    @callback
    def _on_update_cb(self, value: Any) -> None:
        self._attr_native_value = VictronSensor._normalize_value(value)
        self.async_write_ha_state()

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        """Normalize Victron enum values to their enum code."""
        if isinstance(value, VictronEnum):
            return value.id
        return value
