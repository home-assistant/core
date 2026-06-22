"""Sensor platform for the Ouman EH-800 integration."""

from dataclasses import dataclass

from ouman_eh_800_api import (
    L1BaseEndpoints,
    L1RoomSensor,
    L2BaseEndpoints,
    L2RoomSensor,
    OumanEndpoint,
    SystemEndpoints,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import OumanDevice
from .coordinator import OumanEh800ConfigEntry
from .entity import OumanEh800Entity, OumanEh800EntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OumanEh800SensorDescription(OumanEh800EntityDescription, SensorEntityDescription):
    """Sensor description with main/L1/L2 device assignment."""


def _temperature_sensor(
    *,
    device: OumanDevice,
    key: str,
    device_class: SensorDeviceClass = SensorDeviceClass.TEMPERATURE,
    entity_category: EntityCategory | None = None,
    enabled_by_default: bool = True,
) -> OumanEh800SensorDescription:
    return OumanEh800SensorDescription(
        device=device,
        key=key,
        translation_key=key,
        device_class=device_class,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_category=entity_category,
        entity_registry_enabled_default=enabled_by_default,
    )


def _percentage_sensor(
    *,
    device: OumanDevice,
    key: str,
) -> OumanEh800SensorDescription:
    return OumanEh800SensorDescription(
        device=device,
        key=key,
        translation_key=key,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
    )


SENSOR_DESCRIPTIONS: dict[OumanEndpoint, OumanEh800SensorDescription] = {
    SystemEndpoints.OUTSIDE_TEMPERATURE: _temperature_sensor(
        device=OumanDevice.MAIN, key="outside_temperature"
    ),
    L1BaseEndpoints.SUPPLY_WATER_TEMPERATURE: _temperature_sensor(
        device=OumanDevice.L1, key="supply_water_temperature"
    ),
    L1BaseEndpoints.VALVE_POSITION: _percentage_sensor(
        device=OumanDevice.L1, key="valve_position"
    ),
    L1BaseEndpoints.SUPPLY_WATER_TEMPERATURE_SETPOINT: _temperature_sensor(
        device=OumanDevice.L1,
        key="supply_water_temperature_setpoint",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    L1BaseEndpoints.CURVE_SUPPLY_WATER_TEMPERATURE: _temperature_sensor(
        device=OumanDevice.L1,
        key="curve_supply_water_temperature",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    L1BaseEndpoints.FINE_ADJUSTMENT_EFFECT: _temperature_sensor(
        device=OumanDevice.L1,
        key="fine_adjustment_effect",
        device_class=SensorDeviceClass.TEMPERATURE_DELTA,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    L1RoomSensor.ROOM_TEMPERATURE: _temperature_sensor(
        device=OumanDevice.L1, key="room_temperature"
    ),
    L1RoomSensor.ROOM_TEMPERATURE_SETPOINT: _temperature_sensor(
        device=OumanDevice.L1,
        key="room_temperature_setpoint",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    L1RoomSensor.DELAYED_ROOM_TEMPERATURE: _temperature_sensor(
        device=OumanDevice.L1,
        key="delayed_room_temperature",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    L1RoomSensor.ROOM_SENSOR_POTENTIOMETER: _temperature_sensor(
        device=OumanDevice.L1,
        key="room_sensor_potentiometer",
        device_class=SensorDeviceClass.TEMPERATURE_DELTA,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    L2BaseEndpoints.SUPPLY_WATER_TEMPERATURE: _temperature_sensor(
        device=OumanDevice.L2, key="supply_water_temperature"
    ),
    L2BaseEndpoints.VALVE_POSITION: _percentage_sensor(
        device=OumanDevice.L2, key="valve_position"
    ),
    L2BaseEndpoints.SUPPLY_WATER_TEMPERATURE_SETPOINT: _temperature_sensor(
        device=OumanDevice.L2,
        key="supply_water_temperature_setpoint",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    L2BaseEndpoints.CURVE_SUPPLY_WATER_TEMPERATURE: _temperature_sensor(
        device=OumanDevice.L2,
        key="curve_supply_water_temperature",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    L2BaseEndpoints.DELAYED_OUTDOOR_TEMPERATURE_EFFECT: _temperature_sensor(
        device=OumanDevice.L2,
        key="delayed_outdoor_temperature_effect",
        device_class=SensorDeviceClass.TEMPERATURE_DELTA,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    L2RoomSensor.ROOM_TEMPERATURE: _temperature_sensor(
        device=OumanDevice.L2, key="room_temperature"
    ),
    L2RoomSensor.ROOM_TEMPERATURE_SETPOINT: _temperature_sensor(
        device=OumanDevice.L2,
        key="room_temperature_setpoint",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    L2RoomSensor.DELAYED_ROOM_TEMPERATURE: _temperature_sensor(
        device=OumanDevice.L2,
        key="delayed_room_temperature",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OumanEh800ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ouman EH-800 sensors based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        OumanEh800SensorEntity(coordinator, endpoint, description)
        for endpoint in coordinator.data
        if (description := SENSOR_DESCRIPTIONS.get(endpoint)) is not None
    )


class OumanEh800SensorEntity(OumanEh800Entity, SensorEntity):
    """Ouman EH-800 sensor entity."""

    entity_description: OumanEh800SensorDescription

    @property
    def native_value(self) -> float | str:
        """Return the current sensor value."""
        value = self.coordinator.data[self._endpoint]
        assert isinstance(value, float | str)
        return value
