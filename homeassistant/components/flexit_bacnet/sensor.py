"""The Flexit Nordic (BACnet) integration."""
from collections.abc import Callable
from dataclasses import dataclass
import logging

from flexit_bacnet import FlexitBACnet

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
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

from ...helpers.update_coordinator import CoordinatorEntity
from . import FlexitCoordinator
from .const import DOMAIN
from .entity import FlexitEntity

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_SENSOR_FORMAT = (
    SENSOR_DOMAIN + ".{}_{}"
)  # should use f"{some_value} {some_other_value}"


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
        translation_key="exhaust_air_temperaturee",
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
        # device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        # suggested_unit_of_measurement= UnitOfTime.MINUTES,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        translation_key="fireplace_ventilation_remaining_duration",
        value_fn=lambda data: data.fireplace_ventilation_remaining_duration,
        suggested_display_precision=0,
    ),
    FlexitSensorEntityDescription(
        key="rapid_ventilation_remaining_duration",
        state_class=SensorStateClass.MEASUREMENT,
        # suggested_unit_of_measurement= UnitOfTime.MINUTES,
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
        # unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.supply_air_fan_control_signal,
    ),
    # What sensor type should be used for this sensor?
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
    # This does not make sense to be a sensor, since it's value is always the same, i.e. 0.8 kW
    # Could this be added as some form of extra attribute somewhere?
    # FlexitSensorEntityDescription(
    #     key="electric_heater_nominal_power",
    #     device_class=SensorDeviceClass.POWER,
    #     native_unit_of_measurement=UnitOfPower.KILO_WATT,
    #     translation_key="electric_heater_nominal_power",
    #     value_fn=lambda data: data.electric_heater_nominal_power,
    #     suggested_display_precision=3,
    # ),
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
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key="air_filter_operating_time",
        value_fn=lambda data: data.air_filter_operating_time,
        # should we have a last_reset?
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

# These attributes are already in the climate entity
#   operation_mode
#   ventilation_mode

# Comfort button state: shows true or false if the hvac is in mode HOME or AWAY, and is probably not needed as a sensor
# room humidity 1,2,3: gives readings if extra wireless hardware is installed (so not needed)
# If the sensor with bacnet address 59 is non existent use 95 AND 96 for in machine humidity sensors

# These attributes exist in flexit_bacnet but seem too redundant as sensors since they almost never change
#   air_temp_setpoint_away
#   air_temp_setpoint_home
#   fan_setpoint_supply_air_home
#   fan_setpoint_extract_air_home
#   fan_setpoint_supply_air_high
#   fan_setpoint_extract_air_high
#   fan_setpoint_supply_air_away
#   fan_setpoint_extract_air_away
#   fan_setpoint_supply_air_cooker
#   fan_setpoint_extract_air_cooker
#   fan_setpoint_supply_air_fire
#   fan_setpoint_extract_air_fire
#   air_filter_exchange_interval


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Flexit (bacnet) sensor from a config entry."""
    coordinator: FlexitCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    _LOGGER.info("Setting up Flexit (bacnet) sensor from a config entry")

    async_add_entities(
        [
            FlexitSensor(coordinator, description, config_entry.entry_id)
            for description in SENSOR_TYPES
        ]
    )

    # TODO: unsubscribe on remove


class FlexitSensor(FlexitEntity, CoordinatorEntity, SensorEntity):
    """Representation of a Flexit Sensor."""

    # Should it have a name?
    # _attr_name = None

    # Should it have a entity_name?
    # _attr_has_entity_name = True

    # Poll is default

    entity_description: FlexitSensorEntityDescription

    def __init__(
        self,
        coordinator: FlexitCoordinator,
        entity_description: FlexitSensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize Flexit (bacnet) sensor."""
        super().__init__(coordinator)

        _LOGGER.info("Initialize Flexit (bacnet) sensor %s", entity_description.key)

        self.entity_description = entity_description
        self.entity_id = ENTITY_ID_SENSOR_FORMAT.format(
            coordinator.device.device_name, entity_description.key
        )
        self._attr_unique_id = f"{entry_id}-{entity_description.key}"

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
