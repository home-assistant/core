"""Constants for the opentherm_gw integration."""
from __future__ import annotations

from dataclasses import dataclass

import pyotgw.vars as gw_vars

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)

ATTR_GW_ID = "gateway_id"
ATTR_LEVEL = "level"
ATTR_DHW_OVRD = "dhw_override"
ATTR_CH_OVRD = "ch_override"

CONF_CLIMATE = "climate"
CONF_FLOOR_TEMP = "floor_temperature"
CONF_PRECISION = "precision"
CONF_READ_PRECISION = "read_precision"
CONF_SET_PRECISION = "set_precision"
CONF_TEMPORARY_OVRD_MODE = "temporary_override_mode"

CONNECTION_TIMEOUT = 10

DATA_GATEWAYS = "gateways"
DATA_OPENTHERM_GW = "opentherm_gw"

DOMAIN = "opentherm_gw"

SERVICE_RESET_GATEWAY = "reset_gateway"
SERVICE_SET_CH_OVRD = "set_central_heating_ovrd"
SERVICE_SET_CLOCK = "set_clock"
SERVICE_SET_CONTROL_SETPOINT = "set_control_setpoint"
SERVICE_SET_HOT_WATER_SETPOINT = "set_hot_water_setpoint"
SERVICE_SET_HOT_WATER_OVRD = "set_hot_water_ovrd"
SERVICE_SET_GPIO_MODE = "set_gpio_mode"
SERVICE_SET_LED_MODE = "set_led_mode"
SERVICE_SET_MAX_MOD = "set_max_modulation"
SERVICE_SET_OAT = "set_outside_temperature"
SERVICE_SET_SB_TEMP = "set_setback_temperature"

TRANSLATE_SOURCE = {
    gw_vars.BOILER: "Boiler",
    gw_vars.OTGW: None,
    gw_vars.THERMOSTAT: "Thermostat",
}


@dataclass
class OpenThermEntityDescriptionMixin:
    """Mixin for describing OpenTherm Gateway entities."""

    key: str  # OpenTherm variable identifier
    friendly_name_format: str
    status_sources: list[str]


@dataclass
class OpenThermBinarySensorDescription(
    BinarySensorEntityDescription, OpenThermEntityDescriptionMixin
):
    """Class describing OpenTherm Gateway binary sensor entities."""


BINARY_SENSOR_INFO: list[OpenThermBinarySensorDescription] = [
    OpenThermBinarySensorDescription(
        gw_vars.DATA_MASTER_CH_ENABLED,
        "Thermostat Central Heating {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_MASTER_DHW_ENABLED,
        "Thermostat Hot Water {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_MASTER_COOLING_ENABLED,
        "Thermostat Cooling {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_MASTER_OTC_ENABLED,
        "Thermostat Outside Temperature Correction {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_MASTER_CH2_ENABLED,
        "Thermostat Central Heating 2 {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_FAULT_IND,
        "Boiler Fault {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_CH_ACTIVE,
        "Boiler Central Heating {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_DHW_ACTIVE,
        "Boiler Hot Water {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_FLAME_ON,
        "Boiler Flame {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_COOLING_ACTIVE,
        "Boiler Cooling {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=BinarySensorDeviceClass.COLD,
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_CH2_ACTIVE,
        "Boiler Central Heating 2 {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_DIAG_IND,
        "Boiler Diagnostics {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_DHW_PRESENT,
        "Boiler Hot Water Present {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_CONTROL_TYPE,
        "Boiler Control Type {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_COOLING_SUPPORTED,
        "Boiler Cooling Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_DHW_CONFIG,
        "Boiler Hot Water Configuration {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_MASTER_LOW_OFF_PUMP,
        "Boiler Pump Commands Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_CH2_PRESENT,
        "Boiler Central Heating 2 Present {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_SERVICE_REQ,
        "Boiler Service Required {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_REMOTE_RESET,
        "Boiler Remote Reset Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_LOW_WATER_PRESS,
        "Boiler Low Water Pressure {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_GAS_FAULT,
        "Boiler Gas Fault {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_AIR_PRESS_FAULT,
        "Boiler Air Pressure Fault {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_SLAVE_WATER_OVERTEMP,
        "Boiler Water Overtemperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_REMOTE_TRANSFER_DHW,
        "Remote Hot Water Setpoint Transfer Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_REMOTE_TRANSFER_MAX_CH,
        "Remote Maximum Central Heating Setpoint Write Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_REMOTE_RW_DHW,
        "Remote Hot Water Setpoint Write Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_REMOTE_RW_MAX_CH,
        "Remote Central Heating Setpoint Write Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_ROVRD_MAN_PRIO,
        "Remote Override Manual Change Priority {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.DATA_ROVRD_AUTO_PRIO,
        "Remote Override Program Change Priority {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermBinarySensorDescription(
        gw_vars.OTGW_GPIO_A_STATE, "Gateway GPIO A {}", [gw_vars.OTGW]
    ),
    OpenThermBinarySensorDescription(
        gw_vars.OTGW_GPIO_B_STATE, "Gateway GPIO B {}", [gw_vars.OTGW]
    ),
    OpenThermBinarySensorDescription(
        gw_vars.OTGW_IGNORE_TRANSITIONS, "Gateway Ignore Transitions {}", [gw_vars.OTGW]
    ),
    OpenThermBinarySensorDescription(
        gw_vars.OTGW_OVRD_HB, "Gateway Override High Byte {}", [gw_vars.OTGW]
    ),
]


@dataclass
class OpenThermSensorDescription(
    SensorEntityDescription, OpenThermEntityDescriptionMixin
):
    """Class describing OpenTherm Gateway sensor entities."""


SENSOR_INFO: list[OpenThermSensorDescription] = [
    OpenThermSensorDescription(
        gw_vars.DATA_CONTROL_SETPOINT,
        "Control Setpoint {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_MASTER_MEMBERID,
        "Thermostat Member ID {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_SLAVE_MEMBERID,
        "Boiler Member ID {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_SLAVE_OEM_FAULT,
        "Boiler OEM Fault Code {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_COOLING_CONTROL,
        "Cooling Control Signal {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        native_unit_of_measurement=PERCENTAGE,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_CONTROL_SETPOINT_2,
        "Control Setpoint 2 {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_ROOM_SETPOINT_OVRD,
        "Room Setpoint Override {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_SLAVE_MAX_RELATIVE_MOD,
        "Boiler Maximum Relative Modulation {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        native_unit_of_measurement=PERCENTAGE,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_SLAVE_MAX_CAPACITY,
        "Boiler Maximum Capacity {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_SLAVE_MIN_MOD_LEVEL,
        "Boiler Minimum Modulation Level {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        native_unit_of_measurement=PERCENTAGE,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_ROOM_SETPOINT,
        "Room Setpoint {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_REL_MOD_LEVEL,
        "Relative Modulation Level {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        native_unit_of_measurement=PERCENTAGE,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_CH_WATER_PRESS,
        "Central Heating Water Pressure {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_DHW_FLOW_RATE,
        "Hot Water Flow Rate {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        native_unit_of_measurement=f"{UnitOfVolume.LITERS}/{UnitOfTime.MINUTES}",
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_ROOM_SETPOINT_2,
        "Room Setpoint 2 {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_ROOM_TEMP,
        "Room Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_CH_WATER_TEMP,
        "Central Heating Water Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_DHW_TEMP,
        "Hot Water Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_OUTSIDE_TEMP,
        "Outside Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_RETURN_WATER_TEMP,
        "Return Water Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_SOLAR_STORAGE_TEMP,
        "Solar Storage Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_SOLAR_COLL_TEMP,
        "Solar Collector Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_CH_WATER_TEMP_2,
        "Central Heating 2 Water Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_DHW_TEMP_2,
        "Hot Water 2 Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_EXHAUST_TEMP,
        "Exhaust Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_SLAVE_DHW_MAX_SETP,
        "Hot Water Maximum Setpoint {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_SLAVE_DHW_MIN_SETP,
        "Hot Water Minimum Setpoint {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_SLAVE_CH_MAX_SETP,
        "Boiler Maximum Central Heating Setpoint {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_SLAVE_CH_MIN_SETP,
        "Boiler Minimum Central Heating Setpoint {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_DHW_SETPOINT,
        "Hot Water Setpoint {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_MAX_CH_SETPOINT,
        "Maximum Central Heating Setpoint {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_OEM_DIAG,
        "OEM Diagnostic Code {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_TOTAL_BURNER_STARTS,
        "Total Burner Starts {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_CH_PUMP_STARTS,
        "Central Heating Pump Starts {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_DHW_PUMP_STARTS,
        "Hot Water Pump Starts {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_DHW_BURNER_STARTS,
        "Hot Water Burner Starts {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_TOTAL_BURNER_HOURS,
        "Total Burner Hours {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_CH_PUMP_HOURS,
        "Central Heating Pump Hours {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_DHW_PUMP_HOURS,
        "Hot Water Pump Hours {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_DHW_BURNER_HOURS,
        "Hot Water Burner Hours {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_MASTER_OT_VERSION,
        "Thermostat OpenTherm Version {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_SLAVE_OT_VERSION,
        "Boiler OpenTherm Version {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_MASTER_PRODUCT_TYPE,
        "Thermostat Product Type {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_MASTER_PRODUCT_VERSION,
        "Thermostat Product Version {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_SLAVE_PRODUCT_TYPE,
        "Boiler Product Type {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermSensorDescription(
        gw_vars.DATA_SLAVE_PRODUCT_VERSION,
        "Boiler Product Version {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_MODE, "Gateway/Monitor Mode {}", [gw_vars.OTGW]
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_DHW_OVRD, "Gateway Hot Water Override Mode {}", [gw_vars.OTGW]
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_ABOUT, "Gateway Firmware Version {}", [gw_vars.OTGW]
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_BUILD, "Gateway Firmware Build {}", [gw_vars.OTGW]
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_CLOCKMHZ, "Gateway Clock Speed {}", [gw_vars.OTGW]
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_LED_A, "Gateway LED A Mode {}", [gw_vars.OTGW]
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_LED_B, "Gateway LED B Mode {}", [gw_vars.OTGW]
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_LED_C, "Gateway LED C Mode {}", [gw_vars.OTGW]
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_LED_D, "Gateway LED D Mode {}", [gw_vars.OTGW]
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_LED_E, "Gateway LED E Mode {}", [gw_vars.OTGW]
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_LED_F, "Gateway LED F Mode {}", [gw_vars.OTGW]
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_GPIO_A, "Gateway GPIO A Mode {}", [gw_vars.OTGW]
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_GPIO_B, "Gateway GPIO B Mode {}", [gw_vars.OTGW]
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_SB_TEMP,
        "Gateway Setback Temperature {}",
        [gw_vars.OTGW],
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_SETP_OVRD_MODE,
        "Gateway Room Setpoint Override Mode {}",
        [gw_vars.OTGW],
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_SMART_PWR, "Gateway Smart Power Mode {}", [gw_vars.OTGW]
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_THRM_DETECT, "Gateway Thermostat Detection {}", [gw_vars.OTGW]
    ),
    OpenThermSensorDescription(
        gw_vars.OTGW_VREF, "Gateway Reference Voltage Setting {}", [gw_vars.OTGW]
    ),
]

DEPRECATED_BINARY_SENSOR_SOURCE_LOOKUP = {
    gw_vars.DATA_MASTER_CH_ENABLED: gw_vars.THERMOSTAT,
    gw_vars.DATA_MASTER_DHW_ENABLED: gw_vars.THERMOSTAT,
    gw_vars.DATA_MASTER_OTC_ENABLED: gw_vars.THERMOSTAT,
    gw_vars.DATA_MASTER_CH2_ENABLED: gw_vars.THERMOSTAT,
    gw_vars.DATA_SLAVE_FAULT_IND: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_CH_ACTIVE: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_DHW_ACTIVE: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_FLAME_ON: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_COOLING_ACTIVE: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_CH2_ACTIVE: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_DIAG_IND: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_DHW_PRESENT: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_CONTROL_TYPE: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_COOLING_SUPPORTED: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_DHW_CONFIG: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_MASTER_LOW_OFF_PUMP: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_CH2_PRESENT: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_SERVICE_REQ: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_REMOTE_RESET: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_LOW_WATER_PRESS: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_GAS_FAULT: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_AIR_PRESS_FAULT: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_WATER_OVERTEMP: gw_vars.BOILER,
    gw_vars.DATA_REMOTE_TRANSFER_DHW: gw_vars.BOILER,
    gw_vars.DATA_REMOTE_TRANSFER_MAX_CH: gw_vars.BOILER,
    gw_vars.DATA_REMOTE_RW_DHW: gw_vars.BOILER,
    gw_vars.DATA_REMOTE_RW_MAX_CH: gw_vars.BOILER,
    gw_vars.DATA_ROVRD_MAN_PRIO: gw_vars.THERMOSTAT,
    gw_vars.DATA_ROVRD_AUTO_PRIO: gw_vars.THERMOSTAT,
    gw_vars.OTGW_GPIO_A_STATE: gw_vars.OTGW,
    gw_vars.OTGW_GPIO_B_STATE: gw_vars.OTGW,
    gw_vars.OTGW_IGNORE_TRANSITIONS: gw_vars.OTGW,
    gw_vars.OTGW_OVRD_HB: gw_vars.OTGW,
}

DEPRECATED_SENSOR_SOURCE_LOOKUP = {
    gw_vars.DATA_CONTROL_SETPOINT: gw_vars.BOILER,
    gw_vars.DATA_MASTER_MEMBERID: gw_vars.THERMOSTAT,
    gw_vars.DATA_SLAVE_MEMBERID: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_OEM_FAULT: gw_vars.BOILER,
    gw_vars.DATA_COOLING_CONTROL: gw_vars.BOILER,
    gw_vars.DATA_CONTROL_SETPOINT_2: gw_vars.BOILER,
    gw_vars.DATA_ROOM_SETPOINT_OVRD: gw_vars.THERMOSTAT,
    gw_vars.DATA_SLAVE_MAX_RELATIVE_MOD: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_MAX_CAPACITY: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_MIN_MOD_LEVEL: gw_vars.BOILER,
    gw_vars.DATA_ROOM_SETPOINT: gw_vars.THERMOSTAT,
    gw_vars.DATA_REL_MOD_LEVEL: gw_vars.BOILER,
    gw_vars.DATA_CH_WATER_PRESS: gw_vars.BOILER,
    gw_vars.DATA_DHW_FLOW_RATE: gw_vars.BOILER,
    gw_vars.DATA_ROOM_SETPOINT_2: gw_vars.THERMOSTAT,
    gw_vars.DATA_ROOM_TEMP: gw_vars.THERMOSTAT,
    gw_vars.DATA_CH_WATER_TEMP: gw_vars.BOILER,
    gw_vars.DATA_DHW_TEMP: gw_vars.BOILER,
    gw_vars.DATA_OUTSIDE_TEMP: gw_vars.THERMOSTAT,
    gw_vars.DATA_RETURN_WATER_TEMP: gw_vars.BOILER,
    gw_vars.DATA_SOLAR_STORAGE_TEMP: gw_vars.BOILER,
    gw_vars.DATA_SOLAR_COLL_TEMP: gw_vars.BOILER,
    gw_vars.DATA_CH_WATER_TEMP_2: gw_vars.BOILER,
    gw_vars.DATA_DHW_TEMP_2: gw_vars.BOILER,
    gw_vars.DATA_EXHAUST_TEMP: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_DHW_MAX_SETP: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_DHW_MIN_SETP: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_CH_MAX_SETP: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_CH_MIN_SETP: gw_vars.BOILER,
    gw_vars.DATA_DHW_SETPOINT: gw_vars.BOILER,
    gw_vars.DATA_MAX_CH_SETPOINT: gw_vars.BOILER,
    gw_vars.DATA_OEM_DIAG: gw_vars.BOILER,
    gw_vars.DATA_TOTAL_BURNER_STARTS: gw_vars.BOILER,
    gw_vars.DATA_CH_PUMP_STARTS: gw_vars.BOILER,
    gw_vars.DATA_DHW_PUMP_STARTS: gw_vars.BOILER,
    gw_vars.DATA_DHW_BURNER_STARTS: gw_vars.BOILER,
    gw_vars.DATA_TOTAL_BURNER_HOURS: gw_vars.BOILER,
    gw_vars.DATA_CH_PUMP_HOURS: gw_vars.BOILER,
    gw_vars.DATA_DHW_PUMP_HOURS: gw_vars.BOILER,
    gw_vars.DATA_DHW_BURNER_HOURS: gw_vars.BOILER,
    gw_vars.DATA_MASTER_OT_VERSION: gw_vars.THERMOSTAT,
    gw_vars.DATA_SLAVE_OT_VERSION: gw_vars.BOILER,
    gw_vars.DATA_MASTER_PRODUCT_TYPE: gw_vars.THERMOSTAT,
    gw_vars.DATA_MASTER_PRODUCT_VERSION: gw_vars.THERMOSTAT,
    gw_vars.DATA_SLAVE_PRODUCT_TYPE: gw_vars.BOILER,
    gw_vars.DATA_SLAVE_PRODUCT_VERSION: gw_vars.BOILER,
    gw_vars.OTGW_MODE: gw_vars.OTGW,
    gw_vars.OTGW_DHW_OVRD: gw_vars.OTGW,
    gw_vars.OTGW_ABOUT: gw_vars.OTGW,
    gw_vars.OTGW_BUILD: gw_vars.OTGW,
    gw_vars.OTGW_CLOCKMHZ: gw_vars.OTGW,
    gw_vars.OTGW_LED_A: gw_vars.OTGW,
    gw_vars.OTGW_LED_B: gw_vars.OTGW,
    gw_vars.OTGW_LED_C: gw_vars.OTGW,
    gw_vars.OTGW_LED_D: gw_vars.OTGW,
    gw_vars.OTGW_LED_E: gw_vars.OTGW,
    gw_vars.OTGW_LED_F: gw_vars.OTGW,
    gw_vars.OTGW_GPIO_A: gw_vars.OTGW,
    gw_vars.OTGW_GPIO_B: gw_vars.OTGW,
    gw_vars.OTGW_SB_TEMP: gw_vars.OTGW,
    gw_vars.OTGW_SETP_OVRD_MODE: gw_vars.OTGW,
    gw_vars.OTGW_SMART_PWR: gw_vars.OTGW,
    gw_vars.OTGW_THRM_DETECT: gw_vars.OTGW,
    gw_vars.OTGW_VREF: gw_vars.OTGW,
}
