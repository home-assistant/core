"""Sensor platform for the Fresh-r integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pyfreshr.models import DeviceReadings, DeviceType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FreshrConfigEntry, FreshrReadingsCoordinator
from .entity import FreshrEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class FreshrSensorEntityDescription(SensorEntityDescription):
    """Describes a Fresh-r sensor."""

    value_fn: Callable[[DeviceReadings], StateType]


_T1 = FreshrSensorEntityDescription(
    key="t1",
    translation_key="inside_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda r: r.t1,
)
_T2 = FreshrSensorEntityDescription(
    key="t2",
    translation_key="outside_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda r: r.t2,
)
_CO2 = FreshrSensorEntityDescription(
    key="co2",
    device_class=SensorDeviceClass.CO2,
    native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda r: r.co2,
)
_HUM = FreshrSensorEntityDescription(
    key="hum",
    device_class=SensorDeviceClass.HUMIDITY,
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda r: r.hum,
)
_FLOW = FreshrSensorEntityDescription(
    key="flow",
    translation_key="flow",
    device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
    native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda r: r.flow,
)
_DP = FreshrSensorEntityDescription(
    key="dp",
    translation_key="dew_point",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    entity_registry_enabled_default=False,
    value_fn=lambda r: r.dp,
)
_TEMP = FreshrSensorEntityDescription(
    key="temp",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda r: r.temp,
)

SENSOR_TYPES: dict[DeviceType, tuple[FreshrSensorEntityDescription, ...]] = {
    DeviceType.FRESH_R: (_T1, _T2, _CO2, _HUM, _FLOW, _DP),
    DeviceType.FORWARD: (_T1, _T2, _CO2, _HUM, _FLOW, _DP, _TEMP),
    DeviceType.MONITOR: (_CO2, _HUM, _DP, _TEMP),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FreshrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fresh-r sensors from a config entry."""
    coordinator = config_entry.runtime_data.devices
    known_devices: set[str] = set()

    @callback
    def _check_devices() -> None:
        current = set(coordinator.data)
        removed_ids = known_devices - current
        if removed_ids:
            known_devices.difference_update(removed_ids)
        new_ids = current - known_devices
        if not new_ids:
            return
        known_devices.update(new_ids)
        entities: list[FreshrSensor] = []
        for device_id in new_ids:
            device = coordinator.data[device_id]
            descriptions = SENSOR_TYPES.get(
                device.device_type, SENSOR_TYPES[DeviceType.FRESH_R]
            )
            entities.extend(
                FreshrSensor(
                    config_entry.runtime_data.readings[device_id],
                    description,
                )
                for description in descriptions
            )
        async_add_entities(entities)

    _check_devices()
    config_entry.async_on_unload(coordinator.async_add_listener(_check_devices))


class FreshrSensor(FreshrEntity, SensorEntity):
    """Representation of a Fresh-r sensor."""

    entity_description: FreshrSensorEntityDescription

    def __init__(
        self,
        coordinator: FreshrReadingsCoordinator,
        description: FreshrSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the value from coordinator data."""
        return self.entity_description.value_fn(self.coordinator.data)
