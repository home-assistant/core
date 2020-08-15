"""Constants for the opentherm_gw integration."""
import pyotgw.vars as gw_vars

from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
    TIME_HOURS,
    TIME_MINUTES,
    UNIT_PERCENTAGE,
)

ATTR_GW_ID = "gateway_id"
ATTR_LEVEL = "level"
ATTR_DHW_OVRD = "dhw_override"
ATTR_CH_OVRD = "ch_override"

CONF_CLIMATE = "climate"
CONF_FLOOR_TEMP = "floor_temperature"
CONF_PRECISION = "precision"

DATA_GATEWAYS = "gateways"
DATA_OPENTHERM_GW = "opentherm_gw"

DEVICE_CLASS_COLD = "cold"
DEVICE_CLASS_HEAT = "heat"
DEVICE_CLASS_PROBLEM = "problem"

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

UNIT_BAR = "bar"
UNIT_KW = "kW"
UNIT_L_MIN = f"L/{TIME_MINUTES}"

BINARY_SENSOR_INFO = {
    # [device_class, friendly_name format]
    gw_vars.DATA_MASTER_CH_ENABLED: [None, "Thermostat Central Heating Enabled {}"],
    gw_vars.DATA_MASTER_DHW_ENABLED: [None, "Thermostat Hot Water Enabled {}"],
    gw_vars.DATA_MASTER_COOLING_ENABLED: [None, "Thermostat Cooling Enabled {}"],
    gw_vars.DATA_MASTER_OTC_ENABLED: [
        None,
        "Thermostat Outside Temperature Correction Enabled {}",
    ],
    gw_vars.DATA_MASTER_CH2_ENABLED: [None, "Thermostat Central Heating 2 Enabled {}"],
    gw_vars.DATA_SLAVE_FAULT_IND: [DEVICE_CLASS_PROBLEM, "Boiler Fault Indication {}"],
    gw_vars.DATA_SLAVE_CH_ACTIVE: [
        DEVICE_CLASS_HEAT,
        "Boiler Central Heating Status {}",
    ],
    gw_vars.DATA_SLAVE_DHW_ACTIVE: [DEVICE_CLASS_HEAT, "Boiler Hot Water Status {}"],
    gw_vars.DATA_SLAVE_FLAME_ON: [DEVICE_CLASS_HEAT, "Boiler Flame Status {}"],
    gw_vars.DATA_SLAVE_COOLING_ACTIVE: [DEVICE_CLASS_COLD, "Boiler Cooling Status {}"],
    gw_vars.DATA_SLAVE_CH2_ACTIVE: [
        DEVICE_CLASS_HEAT,
        "Boiler Central Heating 2 Status {}",
    ],
    gw_vars.DATA_SLAVE_DIAG_IND: [
        DEVICE_CLASS_PROBLEM,
        "Boiler Diagnostics Indication {}",
    ],
    gw_vars.DATA_SLAVE_DHW_PRESENT: [None, "Boiler Hot Water Present {}"],
    gw_vars.DATA_SLAVE_CONTROL_TYPE: [None, "Boiler Control Type {}"],
    gw_vars.DATA_SLAVE_COOLING_SUPPORTED: [None, "Boiler Cooling Support {}"],
    gw_vars.DATA_SLAVE_DHW_CONFIG: [None, "Boiler Hot Water Configuration {}"],
    gw_vars.DATA_SLAVE_MASTER_LOW_OFF_PUMP: [None, "Boiler Pump Commands Support {}"],
    gw_vars.DATA_SLAVE_CH2_PRESENT: [None, "Boiler Central Heating 2 Present {}"],
    gw_vars.DATA_SLAVE_SERVICE_REQ: [
        DEVICE_CLASS_PROBLEM,
        "Boiler Service Required {}",
    ],
    gw_vars.DATA_SLAVE_REMOTE_RESET: [None, "Boiler Remote Reset Support {}"],
    gw_vars.DATA_SLAVE_LOW_WATER_PRESS: [
        DEVICE_CLASS_PROBLEM,
        "Boiler Low Water Pressure {}",
    ],
    gw_vars.DATA_SLAVE_GAS_FAULT: [DEVICE_CLASS_PROBLEM, "Boiler Gas Fault {}"],
    gw_vars.DATA_SLAVE_AIR_PRESS_FAULT: [
        DEVICE_CLASS_PROBLEM,
        "Boiler Air Pressure Fault {}",
    ],
    gw_vars.DATA_SLAVE_WATER_OVERTEMP: [
        DEVICE_CLASS_PROBLEM,
        "Boiler Water Overtemperature {}",
    ],
    gw_vars.DATA_REMOTE_TRANSFER_DHW: [
        None,
        "Remote Hot Water Setpoint Transfer Support {}",
    ],
    gw_vars.DATA_REMOTE_TRANSFER_MAX_CH: [
        None,
        "Remote Maximum Central Heating Setpoint Write Support {}",
    ],
    gw_vars.DATA_REMOTE_RW_DHW: [None, "Remote Hot Water Setpoint Write Support {}"],
    gw_vars.DATA_REMOTE_RW_MAX_CH: [
        None,
        "Remote Central Heating Setpoint Write Support {}",
    ],
    gw_vars.DATA_ROVRD_MAN_PRIO: [None, "Remote Override Manual Change Priority {}"],
    gw_vars.DATA_ROVRD_AUTO_PRIO: [None, "Remote Override Program Change Priority {}"],
    gw_vars.OTGW_GPIO_A_STATE: [None, "Gateway GPIO A State {}"],
    gw_vars.OTGW_GPIO_B_STATE: [None, "Gateway GPIO B State {}"],
    gw_vars.OTGW_IGNORE_TRANSITIONS: [None, "Gateway Ignore Transitions {}"],
    gw_vars.OTGW_OVRD_HB: [None, "Gateway Override High Byte {}"],
}

SENSOR_INFO = {
    # [device_class, unit, friendly_name]
    gw_vars.DATA_CONTROL_SETPOINT: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Control Setpoint {}",
    ],
    gw_vars.DATA_MASTER_MEMBERID: [None, None, "Thermostat Member ID {}"],
    gw_vars.DATA_SLAVE_MEMBERID: [None, None, "Boiler Member ID {}"],
    gw_vars.DATA_SLAVE_OEM_FAULT: [None, None, "Boiler OEM Fault Code {}"],
    gw_vars.DATA_COOLING_CONTROL: [None, UNIT_PERCENTAGE, "Cooling Control Signal {}"],
    gw_vars.DATA_CONTROL_SETPOINT_2: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Control Setpoint 2 {}",
    ],
    gw_vars.DATA_ROOM_SETPOINT_OVRD: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Room Setpoint Override {}",
    ],
    gw_vars.DATA_SLAVE_MAX_RELATIVE_MOD: [
        None,
        UNIT_PERCENTAGE,
        "Boiler Maximum Relative Modulation {}",
    ],
    gw_vars.DATA_SLAVE_MAX_CAPACITY: [None, UNIT_KW, "Boiler Maximum Capacity {}"],
    gw_vars.DATA_SLAVE_MIN_MOD_LEVEL: [
        None,
        UNIT_PERCENTAGE,
        "Boiler Minimum Modulation Level {}",
    ],
    gw_vars.DATA_ROOM_SETPOINT: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Room Setpoint {}",
    ],
    gw_vars.DATA_REL_MOD_LEVEL: [None, UNIT_PERCENTAGE, "Relative Modulation Level {}"],
    gw_vars.DATA_CH_WATER_PRESS: [None, UNIT_BAR, "Central Heating Water Pressure {}"],
    gw_vars.DATA_DHW_FLOW_RATE: [None, UNIT_L_MIN, "Hot Water Flow Rate {}"],
    gw_vars.DATA_ROOM_SETPOINT_2: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Room Setpoint 2 {}",
    ],
    gw_vars.DATA_ROOM_TEMP: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Room Temperature {}",
    ],
    gw_vars.DATA_CH_WATER_TEMP: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Central Heating Water Temperature {}",
    ],
    gw_vars.DATA_DHW_TEMP: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Hot Water Temperature {}",
    ],
    gw_vars.DATA_OUTSIDE_TEMP: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Outside Temperature {}",
    ],
    gw_vars.DATA_RETURN_WATER_TEMP: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Return Water Temperature {}",
    ],
    gw_vars.DATA_SOLAR_STORAGE_TEMP: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Solar Storage Temperature {}",
    ],
    gw_vars.DATA_SOLAR_COLL_TEMP: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Solar Collector Temperature {}",
    ],
    gw_vars.DATA_CH_WATER_TEMP_2: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Central Heating 2 Water Temperature {}",
    ],
    gw_vars.DATA_DHW_TEMP_2: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Hot Water 2 Temperature {}",
    ],
    gw_vars.DATA_EXHAUST_TEMP: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Exhaust Temperature {}",
    ],
    gw_vars.DATA_SLAVE_DHW_MAX_SETP: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Hot Water Maximum Setpoint {}",
    ],
    gw_vars.DATA_SLAVE_DHW_MIN_SETP: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Hot Water Minimum Setpoint {}",
    ],
    gw_vars.DATA_SLAVE_CH_MAX_SETP: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Boiler Maximum Central Heating Setpoint {}",
    ],
    gw_vars.DATA_SLAVE_CH_MIN_SETP: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Boiler Minimum Central Heating Setpoint {}",
    ],
    gw_vars.DATA_DHW_SETPOINT: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Hot Water Setpoint {}",
    ],
    gw_vars.DATA_MAX_CH_SETPOINT: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Maximum Central Heating Setpoint {}",
    ],
    gw_vars.DATA_OEM_DIAG: [None, None, "OEM Diagnostic Code {}"],
    gw_vars.DATA_TOTAL_BURNER_STARTS: [None, None, "Total Burner Starts {}"],
    gw_vars.DATA_CH_PUMP_STARTS: [None, None, "Central Heating Pump Starts {}"],
    gw_vars.DATA_DHW_PUMP_STARTS: [None, None, "Hot Water Pump Starts {}"],
    gw_vars.DATA_DHW_BURNER_STARTS: [None, None, "Hot Water Burner Starts {}"],
    gw_vars.DATA_TOTAL_BURNER_HOURS: [None, TIME_HOURS, "Total Burner Hours {}"],
    gw_vars.DATA_CH_PUMP_HOURS: [None, TIME_HOURS, "Central Heating Pump Hours {}"],
    gw_vars.DATA_DHW_PUMP_HOURS: [None, TIME_HOURS, "Hot Water Pump Hours {}"],
    gw_vars.DATA_DHW_BURNER_HOURS: [None, TIME_HOURS, "Hot Water Burner Hours {}"],
    gw_vars.DATA_MASTER_OT_VERSION: [None, None, "Thermostat OpenTherm Version {}"],
    gw_vars.DATA_SLAVE_OT_VERSION: [None, None, "Boiler OpenTherm Version {}"],
    gw_vars.DATA_MASTER_PRODUCT_TYPE: [None, None, "Thermostat Product Type {}"],
    gw_vars.DATA_MASTER_PRODUCT_VERSION: [None, None, "Thermostat Product Version {}"],
    gw_vars.DATA_SLAVE_PRODUCT_TYPE: [None, None, "Boiler Product Type {}"],
    gw_vars.DATA_SLAVE_PRODUCT_VERSION: [None, None, "Boiler Product Version {}"],
    gw_vars.OTGW_MODE: [None, None, "Gateway/Monitor Mode {}"],
    gw_vars.OTGW_DHW_OVRD: [None, None, "Gateway Hot Water Override Mode {}"],
    gw_vars.OTGW_ABOUT: [None, None, "Gateway Firmware Version {}"],
    gw_vars.OTGW_BUILD: [None, None, "Gateway Firmware Build {}"],
    gw_vars.OTGW_CLOCKMHZ: [None, None, "Gateway Clock Speed {}"],
    gw_vars.OTGW_LED_A: [None, None, "Gateway LED A Mode {}"],
    gw_vars.OTGW_LED_B: [None, None, "Gateway LED B Mode {}"],
    gw_vars.OTGW_LED_C: [None, None, "Gateway LED C Mode {}"],
    gw_vars.OTGW_LED_D: [None, None, "Gateway LED D Mode {}"],
    gw_vars.OTGW_LED_E: [None, None, "Gateway LED E Mode {}"],
    gw_vars.OTGW_LED_F: [None, None, "Gateway LED F Mode {}"],
    gw_vars.OTGW_GPIO_A: [None, None, "Gateway GPIO A Mode {}"],
    gw_vars.OTGW_GPIO_B: [None, None, "Gateway GPIO B Mode {}"],
    gw_vars.OTGW_SB_TEMP: [
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "Gateway Setback Temperature {}",
    ],
    gw_vars.OTGW_SETP_OVRD_MODE: [None, None, "Gateway Room Setpoint Override Mode {}"],
    gw_vars.OTGW_SMART_PWR: [None, None, "Gateway Smart Power Mode {}"],
    gw_vars.OTGW_THRM_DETECT: [None, None, "Gateway Thermostat Detection {}"],
    gw_vars.OTGW_VREF: [None, None, "Gateway Reference Voltage Setting {}"],
}
