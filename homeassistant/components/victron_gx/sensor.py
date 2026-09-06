"""Support for Victron GX sensors."""

import logging
import math
from typing import Any, override

from victron_mqtt import (
    Device as VictronVenusDevice,
    FormulaMetric as VictronFormulaMetric,
    Metric as VictronVenusMetric,
    MetricKind,
    MetricNature,
    MetricType,
    VictronEnum,
)

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import VictronBaseEntity
from .hub import VictronGxConfigEntry

_LOGGER = logging.getLogger(__name__)

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
    MetricType.HUMIDITY: SensorDeviceClass.HUMIDITY,
    MetricType.PRESSURE: SensorDeviceClass.PRESSURE,
    MetricType.DISTANCE: SensorDeviceClass.DISTANCE,
    MetricType.POWER_FACTOR: SensorDeviceClass.POWER_FACTOR,
    MetricType.COST: SensorDeviceClass.MONETARY,
    MetricType.SPEED: SensorDeviceClass.SPEED,
    MetricType.LIQUID_VOLUME: SensorDeviceClass.VOLUME_STORAGE,
    MetricType.DURATION: SensorDeviceClass.DURATION,
    MetricType.ENUM: SensorDeviceClass.ENUM,
    MetricType.IRRADIANCE: SensorDeviceClass.IRRADIANCE,
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


class VictronSensor(VictronBaseEntity, RestoreSensor):
    """Implementation of a Victron GX sensor."""

    _baseline: float | None = None

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
        self._attr_native_value = VictronSensor._normalize_value(metric.value)

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement."""
        return self._resolve_native_unit_of_measurement()

    @callback
    @override
    def _on_update_cb(self, value: Any) -> None:
        # Enum sensors emit non-numeric values; only add the baseline to numeric
        # cumulative values.
        if self._baseline is not None and isinstance(value, int | float):
            value += self._baseline
        self._attr_native_value = VictronSensor._normalize_value(value)
        self.async_write_ha_state()

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        """Normalize Victron enum values to their enum code."""
        if isinstance(value, VictronEnum):
            return value.id
        return value

    @override
    async def async_added_to_hass(self) -> None:
        """Restore persistent state for FormulaMetric energy sensors."""
        # Cumulative FormulaMetric sensors (TOTAL / TOTAL_INCREASING) start from
        # 0 on each HA restart, so we restore the previous accumulated value as a
        # baseline and add new increments on top.
        should_restore = self.state_class in (
            SensorStateClass.TOTAL_INCREASING,
            SensorStateClass.TOTAL,
        ) and isinstance(self._metric, VictronFormulaMetric)
        if not should_restore:
            await super().async_added_to_hass()
            return

        last_sensor_data = await self.async_get_last_sensor_data()
        if last_sensor_data is None or last_sensor_data.native_value is None:
            _LOGGER.debug(
                "Baseline is missing. Probably first load for %s", self.entity_id
            )
            await super().async_added_to_hass()
            return

        if not isinstance(self._attr_native_value, int | float):
            _LOGGER.warning(
                "Cannot restore baseline for %s: current value is %r (expected numeric)",
                self.entity_id,
                self._attr_native_value,
            )
            await super().async_added_to_hass()
            return

        native_value = last_sensor_data.native_value
        # float() accepts nan/inf, but SensorEntity rejects non-finite values.
        if not isinstance(native_value, int | float) or not math.isfinite(native_value):
            _LOGGER.warning(
                "Could not restore state for %s: invalid value '%s' (type: %s)",
                self.entity_id,
                native_value,
                type(native_value).__name__,
            )
            await super().async_added_to_hass()
            return

        self._baseline = float(native_value)
        self._attr_native_value += self._baseline
        _LOGGER.debug(
            "Restored baseline of %.3f for %s", self._baseline, self.entity_id
        )

        await super().async_added_to_hass()
