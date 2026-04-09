"""Support for Victron GX number entities."""

import logging
from typing import Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    Metric as VictronVenusMetric,
    MetricKind,
    MetricType,
    WritableMetric as VictronVenusWritableMetric,
)

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import VictronBaseEntity
from .hub import VictronGxConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

METRIC_TYPE_TO_DEVICE_CLASS: dict[MetricType, NumberDeviceClass] = {
    MetricType.POWER: NumberDeviceClass.POWER,
    MetricType.APPARENT_POWER: NumberDeviceClass.APPARENT_POWER,
    MetricType.ENERGY: NumberDeviceClass.ENERGY,
    MetricType.VOLTAGE: NumberDeviceClass.VOLTAGE,
    MetricType.CURRENT: NumberDeviceClass.CURRENT,
    MetricType.FREQUENCY: NumberDeviceClass.FREQUENCY,
    MetricType.ELECTRIC_STORAGE_PERCENTAGE: NumberDeviceClass.BATTERY,
    MetricType.TEMPERATURE: NumberDeviceClass.TEMPERATURE,
    MetricType.SPEED: NumberDeviceClass.SPEED,
    MetricType.LIQUID_VOLUME: NumberDeviceClass.VOLUME_STORAGE,
    MetricType.DURATION: NumberDeviceClass.DURATION,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VictronGxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Victron GX number entities from a config entry."""
    hub = config_entry.runtime_data

    def on_new_metric(
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
        installation_id: str,
    ) -> None:
        """Handle new number metric discovery."""
        if not isinstance(metric, VictronVenusWritableMetric):
            _LOGGER.warning(
                "Skipping non-writable metric for device %s",
                device.unique_id,
            )
            return
        async_add_entities(
            [VictronNumber(device, metric, device_info, installation_id)]
        )

    hub.register_new_metric_callback(MetricKind.NUMBER, on_new_metric)


class VictronNumber(VictronBaseEntity, NumberEntity):
    """Implementation of a Victron GX number entity."""

    def __init__(
        self,
        device: VictronVenusDevice,
        metric: VictronVenusWritableMetric,
        device_info: DeviceInfo,
        installation_id: str,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(device, metric, device_info, installation_id)
        self._attr_device_class = METRIC_TYPE_TO_DEVICE_CLASS.get(metric.metric_type)
        if self._attr_device_class is not None:
            self._attr_native_unit_of_measurement = metric.unit_of_measurement
        self._attr_native_value = metric.value
        if isinstance(metric.min_value, int | float):
            self._attr_native_min_value = metric.min_value
        if isinstance(metric.max_value, int | float):
            self._attr_native_max_value = metric.max_value
        if isinstance(metric.step, int | float):
            self._attr_native_step = metric.step

    @callback
    def _on_update_cb(self, value: Any) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()

    def set_native_value(self, value: float) -> None:
        """Set a new value."""
        if not isinstance(self._metric, VictronVenusWritableMetric):
            _LOGGER.error(
                "Cannot set value for non-writable metric %s",
                self._attr_unique_id,
            )
            return
        self._metric.set(value)
