"""Support for Victron GX binary sensors."""

from typing import Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    Metric as VictronVenusMetric,
    MetricKind,
    MetricType,
    VictronEnum,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BINARY_SENSOR_OFF_ID, BINARY_SENSOR_ON_ID
from .entity import VictronBaseEntity
from .hub import VictronGxConfigEntry

PARALLEL_UPDATES = 0  # There is no I/O in the entity itself.

METRIC_TYPE_TO_DEVICE_CLASS: dict[MetricType, BinarySensorDeviceClass] = {
    MetricType.POWER: BinarySensorDeviceClass.POWER,
    MetricType.PROBLEM: BinarySensorDeviceClass.PROBLEM,
    MetricType.CONNECTIVITY: BinarySensorDeviceClass.CONNECTIVITY,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VictronGxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Victron GX binary sensors from a config entry."""
    hub = config_entry.runtime_data

    def on_new_metric(
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
        installation_id: str,
    ) -> None:
        """Handle new binary sensor metric discovery."""
        async_add_entities(
            [VictronBinarySensor(device, metric, device_info, installation_id)]
        )

    hub.register_new_metric_callback(MetricKind.BINARY_SENSOR, on_new_metric)


class VictronBinarySensor(VictronBaseEntity, BinarySensorEntity):
    """Implementation of a Victron GX binary sensor."""

    def __init__(
        self,
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
        installation_id: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(device, metric, device_info, installation_id)
        self._attr_device_class = METRIC_TYPE_TO_DEVICE_CLASS.get(metric.metric_type)
        self._attr_is_on = self.convert_metric_value_to_is_on(metric.value)

    @callback
    def _on_update_cb(self, value: Any) -> None:
        self._attr_is_on = self.convert_metric_value_to_is_on(value)
        self.async_write_ha_state()

    @staticmethod
    def convert_metric_value_to_is_on(value: Any) -> bool | None:
        """Convert a Victron on/off enum value to a boolean."""
        if value is None or not isinstance(value, VictronEnum):
            return None
        if value.id == BINARY_SENSOR_ON_ID:
            return True
        if value.id == BINARY_SENSOR_OFF_ID:
            return False
        return None
