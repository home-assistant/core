"""Constants for the opentherm_gw integration."""

from __future__ import annotations

import pyotgw.vars as gw_vars

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)

ATTR_GW_ID = "gateway_id"
ATTR_LEVEL = "level"
ATTR_DHW_OVRD = "dhw_override"
ATTR_CH_OVRD = "ch_override"
ATTR_TRANSP_CMD = "transp_cmd"
ATTR_TRANSP_ARG = "transp_arg"

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
SERVICE_SEND_TRANSP_CMD = "send_transparent_command"

TRANSLATE_SOURCE = {
    gw_vars.BOILER: "Boiler",
    gw_vars.OTGW: None,
    gw_vars.THERMOSTAT: "Thermostat",
}

SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION = 1

BINARY_SENSOR_INFO: dict[str, list] = {
    # [device_class, friendly_name format, [status source, ...]]
    gw_vars.DATA_MASTER_CH_ENABLED: [
        None,
        "Thermostat Central Heating {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MASTER_DHW_ENABLED: [
        None,
        "Thermostat Hot Water {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MASTER_COOLING_ENABLED: [
        None,
        "Thermostat Cooling {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MASTER_OTC_ENABLED: [
        None,
        "Thermostat Outside Temperature Correction {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MASTER_CH2_ENABLED: [
        None,
        "Thermostat Central Heating 2 {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_FAULT_IND: [
        BinarySensorDeviceClass.PROBLEM,
        "Boiler Fault {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_CH_ACTIVE: [
        BinarySensorDeviceClass.HEAT,
        "Boiler Central Heating {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_DHW_ACTIVE: [
        BinarySensorDeviceClass.HEAT,
        "Boiler Hot Water {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_FLAME_ON: [
        BinarySensorDeviceClass.HEAT,
        "Boiler Flame {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_COOLING_ACTIVE: [
        BinarySensorDeviceClass.COLD,
        "Boiler Cooling {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_CH2_ACTIVE: [
        BinarySensorDeviceClass.HEAT,
        "Boiler Central Heating 2 {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_DIAG_IND: [
        BinarySensorDeviceClass.PROBLEM,
        "Boiler Diagnostics {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_DHW_PRESENT: [
        None,
        "Boiler Hot Water Present {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_CONTROL_TYPE: [
        None,
        "Boiler Control Type {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_COOLING_SUPPORTED: [
        None,
        "Boiler Cooling Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_DHW_CONFIG: [
        None,
        "Boiler Hot Water Configuration {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_MASTER_LOW_OFF_PUMP: [
        None,
        "Boiler Pump Commands Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_CH2_PRESENT: [
        None,
        "Boiler Central Heating 2 Present {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_SERVICE_REQ: [
        BinarySensorDeviceClass.PROBLEM,
        "Boiler Service Required {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_REMOTE_RESET: [
        None,
        "Boiler Remote Reset Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_LOW_WATER_PRESS: [
        BinarySensorDeviceClass.PROBLEM,
        "Boiler Low Water Pressure {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_GAS_FAULT: [
        BinarySensorDeviceClass.PROBLEM,
        "Boiler Gas Fault {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_AIR_PRESS_FAULT: [
        BinarySensorDeviceClass.PROBLEM,
        "Boiler Air Pressure Fault {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_WATER_OVERTEMP: [
        BinarySensorDeviceClass.PROBLEM,
        "Boiler Water Overtemperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_REMOTE_TRANSFER_DHW: [
        None,
        "Remote Hot Water Setpoint Transfer Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_REMOTE_TRANSFER_MAX_CH: [
        None,
        "Remote Maximum Central Heating Setpoint Write Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_REMOTE_RW_DHW: [
        None,
        "Remote Hot Water Setpoint Write Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_REMOTE_RW_MAX_CH: [
        None,
        "Remote Central Heating Setpoint Write Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_ROVRD_MAN_PRIO: [
        None,
        "Remote Override Manual Change Priority {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_ROVRD_AUTO_PRIO: [
        None,
        "Remote Override Program Change Priority {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.OTGW_GPIO_A_STATE: [None, "Gateway GPIO A {}", [gw_vars.OTGW]],
    gw_vars.OTGW_GPIO_B_STATE: [None, "Gateway GPIO B {}", [gw_vars.OTGW]],
    gw_vars.OTGW_IGNORE_TRANSITIONS: [
        None,
        "Gateway Ignore Transitions {}",
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_OVRD_HB: [None, "Gateway Override High Byte {}", [gw_vars.OTGW]],
}

SENSOR_INFO: dict[str, list] = {
    # [device_class, unit, friendly_name, suggested_display_precision, [status source, ...]]
    gw_vars.DATA_CONTROL_SETPOINT: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Control Setpoint {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MASTER_MEMBERID: [
        None,
        None,
        "Thermostat Member ID {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_MEMBERID: [
        None,
        None,
        "Boiler Member ID {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_OEM_FAULT: [
        None,
        None,
        "Boiler OEM Fault Code {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_COOLING_CONTROL: [
        None,
        PERCENTAGE,
        "Cooling Control Signal {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_CONTROL_SETPOINT_2: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Control Setpoint 2 {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_ROOM_SETPOINT_OVRD: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Room Setpoint Override {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_MAX_RELATIVE_MOD: [
        None,
        PERCENTAGE,
        "Boiler Maximum Relative Modulation {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_MAX_CAPACITY: [
        SensorDeviceClass.POWER,
        UnitOfPower.KILO_WATT,
        "Boiler Maximum Capacity {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_MIN_MOD_LEVEL: [
        None,
        PERCENTAGE,
        "Boiler Minimum Modulation Level {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_ROOM_SETPOINT: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Room Setpoint {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_REL_MOD_LEVEL: [
        None,
        PERCENTAGE,
        "Relative Modulation Level {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_CH_WATER_PRESS: [
        SensorDeviceClass.PRESSURE,
        UnitOfPressure.BAR,
        "Central Heating Water Pressure {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_DHW_FLOW_RATE: [
        SensorDeviceClass.VOLUME_FLOW_RATE,
        UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        "Hot Water Flow Rate {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_ROOM_SETPOINT_2: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Room Setpoint 2 {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_ROOM_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Room Temperature {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_CH_WATER_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Central Heating Water Temperature {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_DHW_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Hot Water Temperature {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_OUTSIDE_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Outside Temperature {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_RETURN_WATER_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Return Water Temperature {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SOLAR_STORAGE_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Solar Storage Temperature {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SOLAR_COLL_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Solar Collector Temperature {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_CH_WATER_TEMP_2: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Central Heating 2 Water Temperature {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_DHW_TEMP_2: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Hot Water 2 Temperature {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_EXHAUST_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Exhaust Temperature {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_DHW_MAX_SETP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Hot Water Maximum Setpoint {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_DHW_MIN_SETP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Hot Water Minimum Setpoint {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_CH_MAX_SETP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Boiler Maximum Central Heating Setpoint {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_CH_MIN_SETP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Boiler Minimum Central Heating Setpoint {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_DHW_SETPOINT: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Hot Water Setpoint {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MAX_CH_SETPOINT: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Maximum Central Heating Setpoint {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_OEM_DIAG: [
        None,
        None,
        "OEM Diagnostic Code {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_TOTAL_BURNER_STARTS: [
        None,
        "starts",
        "Total Burner Starts {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_CH_PUMP_STARTS: [
        None,
        "starts",
        "Central Heating Pump Starts {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_DHW_PUMP_STARTS: [
        None,
        "starts",
        "Hot Water Pump Starts {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_DHW_BURNER_STARTS: [
        None,
        "starts",
        "Hot Water Burner Starts {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_TOTAL_BURNER_HOURS: [
        SensorDeviceClass.DURATION,
        UnitOfTime.HOURS,
        "Total Burner Hours {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_CH_PUMP_HOURS: [
        SensorDeviceClass.DURATION,
        UnitOfTime.HOURS,
        "Central Heating Pump Hours {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_DHW_PUMP_HOURS: [
        SensorDeviceClass.DURATION,
        UnitOfTime.HOURS,
        "Hot Water Pump Hours {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_DHW_BURNER_HOURS: [
        SensorDeviceClass.DURATION,
        UnitOfTime.HOURS,
        "Hot Water Burner Hours {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MASTER_OT_VERSION: [
        None,
        None,
        "Thermostat OpenTherm Version {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_OT_VERSION: [
        None,
        None,
        "Boiler OpenTherm Version {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MASTER_PRODUCT_TYPE: [
        None,
        None,
        "Thermostat Product Type {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MASTER_PRODUCT_VERSION: [
        None,
        None,
        "Thermostat Product Version {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_PRODUCT_TYPE: [
        None,
        None,
        "Boiler Product Type {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_PRODUCT_VERSION: [
        None,
        None,
        "Boiler Product Version {}",
        None,
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.OTGW_MODE: [
        None,
        None,
        "Gateway/Monitor Mode {}",
        None,
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_DHW_OVRD: [
        None,
        None,
        "Gateway Hot Water Override Mode {}",
        None,
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_ABOUT: [
        None,
        None,
        "Gateway Firmware Version {}",
        None,
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_BUILD: [
        None,
        None,
        "Gateway Firmware Build {}",
        None,
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_CLOCKMHZ: [
        None,
        None,
        "Gateway Clock Speed {}",
        None,
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_LED_A: [
        None,
        None,
        "Gateway LED A Mode {}",
        None,
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_LED_B: [
        None,
        None,
        "Gateway LED B Mode {}",
        None,
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_LED_C: [
        None,
        None,
        "Gateway LED C Mode {}",
        None,
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_LED_D: [
        None,
        None,
        "Gateway LED D Mode {}",
        None,
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_LED_E: [
        None,
        None,
        "Gateway LED E Mode {}",
        None,
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_LED_F: [
        None,
        None,
        "Gateway LED F Mode {}",
        None,
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_GPIO_A: [
        None,
        None,
        "Gateway GPIO A Mode {}",
        None,
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_GPIO_B: [
        None,
        None,
        "Gateway GPIO B Mode {}",
        None,
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_SB_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Gateway Setback Temperature {}",
        SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_SETP_OVRD_MODE: [
        None,
        None,
        "Gateway Room Setpoint Override Mode {}",
        None,
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_SMART_PWR: [
        None,
        None,
        "Gateway Smart Power Mode {}",
        None,
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_THRM_DETECT: [
        None,
        None,
        "Gateway Thermostat Detection {}",
        None,
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_VREF: [
        None,
        None,
        "Gateway Reference Voltage Setting {}",
        None,
        [gw_vars.OTGW],
    ],
}
