"""Support for Victron Venus sensors."""

import logging
from typing import Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    FormulaMetric as VictronFormulaMetric,
    Metric as VictronVenusMetric,
    MetricKind,
    MetricNature,
    MetricType,
)

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import VictronBaseEntity
from .hub import Hub, VictronGxConfigEntry

PARALLEL_UPDATES = 0  # There is no I/O in the entity itself.

_LOGGER = logging.getLogger(__name__)

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
    """Set up Victron Venus sensors from a config entry."""
    hub: Hub = config_entry.runtime_data

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


class VictronSensor(VictronBaseEntity, RestoreSensor):
    """Implementation of a Victron Venus sensor."""

    _baseline: float | None = None

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
        self._attr_native_unit_of_measurement = UNIT_MAPPING.get(
            metric.unit_of_measurement, metric.unit_of_measurement
        )

    @callback
    def _on_update_cb(self, value: Any) -> None:
        if self._baseline is not None:
            value += self._baseline
        if self._attr_native_value == value:
            return
        self._attr_native_value = value
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore persistent state for FormulaMetric energy sensors."""

        # Only restore for:
        # 1. Total increasing sensors (like cumulative energy)
        # 2. FormulaMetrics (calculated values)
        should_restore = self.state_class in [
            SensorStateClass.TOTAL_INCREASING,
            SensorStateClass.TOTAL,
        ] and isinstance(self._metric, VictronFormulaMetric)
        self._attr_native_value = self._metric.value
        if not should_restore:
            # Call parent to register update callbacks
            await super().async_added_to_hass()
            return

        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state is not None:
            assert isinstance(self._attr_native_value, (int, float)), (
                "sensor with stored baseline value must be numeric"
            )
            try:
                self._baseline = float(last_state.state)
                self._attr_native_value += self._baseline
                _LOGGER.debug(
                    "Restored baseline of %.3f for %s", self._baseline, self.entity_id
                )
            except ValueError:
                _LOGGER.warning(
                    "Could not restore state for %s: invalid value '%s'",
                    self.entity_id,
                    last_state.state,
                )
        # Call parent to register update callbacks
        await super().async_added_to_hass()
