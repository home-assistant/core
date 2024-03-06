"""The Flexit Nordic (BACnet) integration."""
from collections.abc import Callable
from dataclasses import dataclass

from flexit_bacnet import FlexitBACnet

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FlexitCoordinator
from .const import DOMAIN
from .entity import FlexitEntity


@dataclass(kw_only=True, frozen=True)
class FlexitSensorEntityDescription(SensorEntityDescription):
    """Describes a Flexit sensor entity."""

    value_fn: Callable[[FlexitBACnet], float]


SENSOR_TYPES: tuple[FlexitSensorEntityDescription, ...] = (
    FlexitSensorEntityDescription(
        key="outside_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key="outside_air_temperature",
        value_fn=lambda data: data.outside_air_temperature,
    ),
    FlexitSensorEntityDescription(
        key="supply_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key="supply_air_temperature",
        value_fn=lambda data: data.supply_air_temperature,
    ),
    FlexitSensorEntityDescription(
        key="exhaust_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key="exhaust_air_temperature",
        value_fn=lambda data: data.exhaust_air_temperature,
    ),
    FlexitSensorEntityDescription(
        key="extract_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key="extract_air_temperature",
        value_fn=lambda data: data.extract_air_temperature,
    ),
    FlexitSensorEntityDescription(
        key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key="room_temperature",
        value_fn=lambda data: data.room_temperature,
    ),
    FlexitSensorEntityDescription(
        key="fireplace_ventilation_remaining_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        translation_key="fireplace_ventilation_remaining_duration",
        value_fn=lambda data: data.fireplace_ventilation_remaining_duration,
        suggested_display_precision=0,
    ),
    FlexitSensorEntityDescription(
        key="rapid_ventilation_remaining_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        translation_key="rapid_ventilation_remaining_duration",
        value_fn=lambda data: data.rapid_ventilation_remaining_duration,
        suggested_display_precision=0,
    ),
    FlexitSensorEntityDescription(
        key="supply_air_fan_control_signal",
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="supply_air_fan_control_signal",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.supply_air_fan_control_signal,
    ),
    FlexitSensorEntityDescription(
        key="supply_air_fan_rpm",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        translation_key="supply_air_fan_rpm",
        value_fn=lambda data: data.supply_air_fan_rpm,
    ),
    FlexitSensorEntityDescription(
        key="exhaust_air_fan_control_signal",
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="exhaust_air_fan_control_signal",
        value_fn=lambda data: data.exhaust_air_fan_control_signal,
        native_unit_of_measurement=PERCENTAGE,
    ),
    FlexitSensorEntityDescription(
        key="exhaust_air_fan_rpm",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        translation_key="exhaust_air_fan_rpm",
        value_fn=lambda data: data.exhaust_air_fan_rpm,
    ),
    FlexitSensorEntityDescription(
        key="electric_heater_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        translation_key="electric_heater_power",
        value_fn=lambda data: data.electric_heater_power,
        suggested_display_precision=3,
    ),
    FlexitSensorEntityDescription(
        key="air_filter_operating_time",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key="air_filter_operating_time",
        value_fn=lambda data: data.air_filter_operating_time,
    ),
    FlexitSensorEntityDescription(
        key="heat_exchanger_efficiency",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        translation_key="heat_exchanger_efficiency",
        value_fn=lambda data: data.heat_exchanger_efficiency,
    ),
    FlexitSensorEntityDescription(
        key="heat_exchanger_speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        translation_key="heat_exchanger_speed",
        value_fn=lambda data: data.heat_exchanger_speed,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Flexit (bacnet) sensor from a config entry."""
    coordinator: FlexitCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        FlexitSensor(coordinator, description) for description in SENSOR_TYPES
    )


class FlexitSensor(FlexitEntity, SensorEntity):
    """Representation of a Flexit (bacnet) Sensor."""

    entity_description: FlexitSensorEntityDescription

    def __init__(
        self,
        coordinator: FlexitCoordinator,
        entity_description: FlexitSensorEntityDescription,
    ) -> None:
        """Initialize Flexit (bacnet) sensor."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.device.serial_number}-{entity_description.key}"
        )

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
