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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreshrConfigEntry, FreshrReadingsCoordinator

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

_DEVICE_TYPE_NAMES: dict[DeviceType, str] = {
    DeviceType.FRESH_R: "Fresh-r",
    DeviceType.FORWARD: "Fresh-r Forward",
    DeviceType.MONITOR: "Fresh-r Monitor",
}

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
    entities: list[FreshrSensor] = []
    for device in config_entry.runtime_data.devices.data:
        descriptions = SENSOR_TYPES.get(
            device.device_type, SENSOR_TYPES[DeviceType.FRESH_R]
        )
        device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=_DEVICE_TYPE_NAMES.get(device.device_type, "Fresh-r"),
            serial_number=device.id,
            manufacturer="Fresh-r",
        )
        entities.extend(
            FreshrSensor(
                config_entry.runtime_data.readings[device.id],
                description,
                device_info,
            )
            for description in descriptions
        )
    async_add_entities(entities)


class FreshrSensor(CoordinatorEntity[FreshrReadingsCoordinator], SensorEntity):
    """Representation of a Fresh-r sensor."""

    _attr_has_entity_name = True
    entity_description: FreshrSensorEntityDescription

    def __init__(
        self,
        coordinator: FreshrReadingsCoordinator,
        description: FreshrSensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = device_info
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the value from coordinator data."""
        return self.entity_description.value_fn(self.coordinator.data)
