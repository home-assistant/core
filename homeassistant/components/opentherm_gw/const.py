"""Constants for the opentherm_gw integration."""
from __future__ import annotations

import pyotgw.vars as gw_vars

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
