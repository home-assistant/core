from enum import Enum

class EDeviceCapability(Enum):
    ONOFF = "onoff"
    MEASURE_TEMPERATURE = "measure_temperature"
    TARGET_TEMPERATURE = "target_temperature"
    MEASURE_HUMIDITY = "measure_humidity"
    MEASURE_POWER = "measure_power" 
    MEASURE_DAILY_POWER = "measure_daily_power" 
    INDIVIDUAL_CONTROL = "individual_control"
    CHILD_LOCK = "child_lock"
    COMMERCIAL_LOCK = "commercial_lock" 
    OPEN_WINDOW = "open_window"
    PREDICTIVE_HEATING = "predictive_heating"
    PID_CONTROLLER = "pid_controller"
    SLOW_PID = "slow_pid"
    COOLING_MODE = "cooling_mode" 
    ADJUST_WATTAGE = "adjust_wattage" 
    MEASURE_WATTAGE = "measure_wattage" 

    MEASURE_CO2 = "measure_co2"
    MEASURE_TVOC = "measure_tvoc"
    MEASURE_BATTERY = "measure_battery"

    MEASURE_PM1 = "measure_pm1"
    MEASURE_PM25 = "measure_pm25"
    MEASURE_PM10 = "measure_pm10"
    MEASURE_PARTICLES = "measure_particles" 
    MEASURE_FILTER_STATE = "measure_filter_state" 
    PURIFIER_MODE = "purifier_mode" 

    GREE_MODE = "gree_mode"
    GREE_FAN_SPEED = "gree_fan_speed" 
    GREE_FAN_SPEED_MODE = "fan_mode" 
    GREE_SWEEPING_ANGLE_VERTICAL = "gree_sweeping_angle_vertical"
    GREE_SWEEPING_ANGLE_HORIZONTAL = "gree_sweeping_angle_horisontal" 
    GREE_DISPLAY_LIGHT = "gree_display_light"
    MEASURE_TEMPERATURE_VIRTUAL = "measure_temperature_virtual"


class EDeviceType(Enum):
    SOCKET_GEN2 = "GL-WIFI Socket G2"
    SOCKET_GEN3 = "GL-WIFI Socket G3"
    SOCKET_GEN4 = "GL-WIFI Socket G4"
    SENSE = "GL-Sense"
    PANEL_HEATER_GEN2 = "GL-Panel Heater G2"
    PANEL_HEATER_GEN3 = "GL-Panel Heater G3"
    PANEL_HEATER_GEN3M = "GL-Panel Heater G3 M"
    PANEL_HEATER_GEN3MV2 = "GL-Panel Heater G3 MV2" 
    OIL_HEATER_GEN2 = "GL-Oil Heater G2"
    OIL_HEATER_GEN3 = "GL-Oil Heater G3"
    CONVECTION_HEATER_GEN2 = "GL-Convection Heater G2"
    CONVECTION_HEATER_GEN3 = "GL-Convection Heater G3"
    COMAX = "GL-WIFI Convection MAX 1500W G3" 
    AIR_PURIFIER_M = "GL-Air Purifier M"
    AIR_PURIFIER_L = "GL-Air Purifier L"
    HEATPUMP = "GL-Heat Pump"
    OIL_HEATER_GEN3_V2 = "GL-Oil Heater G3 V2"
    PANEL_HEATER_GEN4 = "GL-Panel Heater G4"

class EOperationMode(Enum):
    WEEKLY_PROGRAM = "weekly_program"
    INDEPENDENT_DEVICE = "independent_device" 
    CONTROL_INDIVIDUALLY = "control_individually"

class EPredictiveHeatingType(Enum):
    OFF = "off"
    ADVANCED = "advanced"

class ELockMode(Enum):
    NO_LOCK = "no_lock"
    CHILD = "child"
    COMMERCIAL = "commercial"

class EAdditionalSocketMode(Enum):
    COOLING = "cooling"

class ERegulatorType(Enum):
    PID = "pid"
    HYSTERESIS_OR_SLOW_PID = "hysteresis_or_slow_pid"
    UNKNOWN = "unknown"

class EPurifierFanMode(Enum):
    AUTO = "AUTO"
    SLEEP = "SLEEP"
    BOOST = "BOOST"
    MANUAL_LEVEL1 = "MANUAL_LEVEL1"
    MANUAL_LEVEL2 = "MANUAL_LEVEL2"
    MANUAL_LEVEL3 = "MANUAL_LEVEL3"
    MANUAL_LEVEL4 = "MANUAL_LEVEL4"
    MANUAL_LEVEL5 = "MANUAL_LEVEL5"
    MANUAL_LEVEL6 = "MANUAL_LEVEL6"
    MANUAL_LEVEL7 = "MANUAL_LEVEL7"
    SOFT_OFF = "SOFT_OFF"
    HARD_OFF = "HARD_OFF"

class EFilterState(Enum):
    OK = "OK"
    MEDIUM_DIRTY = "MEDIUM_DIRTY"
    DIRTY = "DIRTY"
    MUST_BE_CHANGED = "MUST_BE_CHANGED"
    UNKNOWN = "UNKNOWN"

DEVICE_CAPABILITY_MAP: dict[EDeviceType, set[EDeviceCapability]] = {
    EDeviceType.SOCKET_GEN2: {
        EDeviceCapability.ONOFF, EDeviceCapability.TARGET_TEMPERATURE, EDeviceCapability.MEASURE_TEMPERATURE,
        EDeviceCapability.INDIVIDUAL_CONTROL, EDeviceCapability.CHILD_LOCK, EDeviceCapability.OPEN_WINDOW,
        EDeviceCapability.PREDICTIVE_HEATING, EDeviceCapability.MEASURE_DAILY_POWER, EDeviceCapability.MEASURE_POWER,
        EDeviceCapability.MEASURE_TEMPERATURE_VIRTUAL
    },
    EDeviceType.SOCKET_GEN3: {
        EDeviceCapability.ONOFF, EDeviceCapability.TARGET_TEMPERATURE, EDeviceCapability.MEASURE_TEMPERATURE,
        EDeviceCapability.MEASURE_HUMIDITY, EDeviceCapability.INDIVIDUAL_CONTROL, EDeviceCapability.CHILD_LOCK,
        EDeviceCapability.OPEN_WINDOW, EDeviceCapability.PREDICTIVE_HEATING, EDeviceCapability.MEASURE_DAILY_POWER,
        EDeviceCapability.MEASURE_POWER, EDeviceCapability.MEASURE_TEMPERATURE_VIRTUAL
    },
    EDeviceType.SOCKET_GEN4: {
        EDeviceCapability.ONOFF, EDeviceCapability.TARGET_TEMPERATURE, EDeviceCapability.MEASURE_TEMPERATURE,
        EDeviceCapability.MEASURE_HUMIDITY, EDeviceCapability.INDIVIDUAL_CONTROL, EDeviceCapability.CHILD_LOCK,
        EDeviceCapability.OPEN_WINDOW, EDeviceCapability.PREDICTIVE_HEATING, EDeviceCapability.COOLING_MODE,
        EDeviceCapability.MEASURE_DAILY_POWER, EDeviceCapability.MEASURE_POWER, EDeviceCapability.MEASURE_TEMPERATURE_VIRTUAL
    },
    EDeviceType.SENSE: {
        EDeviceCapability.MEASURE_TEMPERATURE, EDeviceCapability.MEASURE_HUMIDITY, EDeviceCapability.MEASURE_CO2,
        EDeviceCapability.MEASURE_TVOC, EDeviceCapability.MEASURE_BATTERY
    },
    EDeviceType.PANEL_HEATER_GEN2: {
        EDeviceCapability.ONOFF, EDeviceCapability.TARGET_TEMPERATURE, EDeviceCapability.MEASURE_TEMPERATURE,
        EDeviceCapability.INDIVIDUAL_CONTROL, EDeviceCapability.CHILD_LOCK, EDeviceCapability.MEASURE_DAILY_POWER,
        EDeviceCapability.MEASURE_POWER
    },
    EDeviceType.PANEL_HEATER_GEN3: {
        EDeviceCapability.ONOFF, EDeviceCapability.TARGET_TEMPERATURE, EDeviceCapability.MEASURE_TEMPERATURE,
        EDeviceCapability.INDIVIDUAL_CONTROL, EDeviceCapability.CHILD_LOCK, EDeviceCapability.COMMERCIAL_LOCK, 
        EDeviceCapability.OPEN_WINDOW, EDeviceCapability.PREDICTIVE_HEATING, EDeviceCapability.ADJUST_WATTAGE, 
        EDeviceCapability.PID_CONTROLLER, EDeviceCapability.SLOW_PID, EDeviceCapability.MEASURE_DAILY_POWER,
        EDeviceCapability.MEASURE_POWER
    },
    EDeviceType.PANEL_HEATER_GEN3M: { 
        EDeviceCapability.ONOFF, EDeviceCapability.TARGET_TEMPERATURE, EDeviceCapability.MEASURE_TEMPERATURE,
        EDeviceCapability.INDIVIDUAL_CONTROL, EDeviceCapability.CHILD_LOCK, EDeviceCapability.COMMERCIAL_LOCK,
        EDeviceCapability.OPEN_WINDOW, EDeviceCapability.PREDICTIVE_HEATING, EDeviceCapability.ADJUST_WATTAGE,
        EDeviceCapability.PID_CONTROLLER, EDeviceCapability.SLOW_PID, EDeviceCapability.MEASURE_DAILY_POWER,
        EDeviceCapability.MEASURE_POWER
    },
    EDeviceType.PANEL_HEATER_GEN3MV2: { 
        EDeviceCapability.ONOFF, EDeviceCapability.TARGET_TEMPERATURE, EDeviceCapability.MEASURE_TEMPERATURE,
        EDeviceCapability.INDIVIDUAL_CONTROL, EDeviceCapability.CHILD_LOCK, EDeviceCapability.COMMERCIAL_LOCK,
        EDeviceCapability.OPEN_WINDOW, EDeviceCapability.PREDICTIVE_HEATING, EDeviceCapability.ADJUST_WATTAGE,
        EDeviceCapability.PID_CONTROLLER, EDeviceCapability.SLOW_PID, EDeviceCapability.MEASURE_DAILY_POWER,
        EDeviceCapability.MEASURE_POWER
    },
    EDeviceType.OIL_HEATER_GEN2: {
        EDeviceCapability.ONOFF, EDeviceCapability.TARGET_TEMPERATURE, EDeviceCapability.MEASURE_TEMPERATURE,
        EDeviceCapability.INDIVIDUAL_CONTROL, EDeviceCapability.CHILD_LOCK,
        EDeviceCapability.MEASURE_DAILY_POWER, EDeviceCapability.MEASURE_POWER 
    },
    EDeviceType.OIL_HEATER_GEN3: {
        EDeviceCapability.ONOFF, EDeviceCapability.TARGET_TEMPERATURE, EDeviceCapability.MEASURE_TEMPERATURE,
        EDeviceCapability.INDIVIDUAL_CONTROL, EDeviceCapability.CHILD_LOCK, EDeviceCapability.COMMERCIAL_LOCK,
        EDeviceCapability.OPEN_WINDOW, EDeviceCapability.PREDICTIVE_HEATING, EDeviceCapability.MEASURE_WATTAGE,
        EDeviceCapability.MEASURE_DAILY_POWER, EDeviceCapability.MEASURE_POWER 
    },
    EDeviceType.CONVECTION_HEATER_GEN2: {
        EDeviceCapability.ONOFF, EDeviceCapability.TARGET_TEMPERATURE, EDeviceCapability.MEASURE_TEMPERATURE,
        EDeviceCapability.INDIVIDUAL_CONTROL, EDeviceCapability.CHILD_LOCK, EDeviceCapability.MEASURE_DAILY_POWER,
        EDeviceCapability.MEASURE_POWER
    },
    EDeviceType.CONVECTION_HEATER_GEN3: {
        EDeviceCapability.ONOFF, EDeviceCapability.TARGET_TEMPERATURE, EDeviceCapability.MEASURE_TEMPERATURE,
        EDeviceCapability.INDIVIDUAL_CONTROL, EDeviceCapability.CHILD_LOCK, EDeviceCapability.COMMERCIAL_LOCK,
        EDeviceCapability.OPEN_WINDOW, EDeviceCapability.PREDICTIVE_HEATING, EDeviceCapability.MEASURE_DAILY_POWER,
        EDeviceCapability.MEASURE_POWER
    },
    EDeviceType.COMAX: { 
        EDeviceCapability.ONOFF, EDeviceCapability.TARGET_TEMPERATURE, EDeviceCapability.MEASURE_TEMPERATURE,
        EDeviceCapability.INDIVIDUAL_CONTROL, EDeviceCapability.CHILD_LOCK, EDeviceCapability.COMMERCIAL_LOCK,
        EDeviceCapability.OPEN_WINDOW, EDeviceCapability.PID_CONTROLLER, EDeviceCapability.SLOW_PID,
        EDeviceCapability.PREDICTIVE_HEATING, EDeviceCapability.ADJUST_WATTAGE, EDeviceCapability.MEASURE_DAILY_POWER,
        EDeviceCapability.MEASURE_POWER
    },
    EDeviceType.AIR_PURIFIER_M: {
        EDeviceCapability.ONOFF, EDeviceCapability.MEASURE_TEMPERATURE, EDeviceCapability.MEASURE_HUMIDITY,
        EDeviceCapability.CHILD_LOCK, EDeviceCapability.MEASURE_PM1, EDeviceCapability.MEASURE_PM25,
        EDeviceCapability.MEASURE_PM10, EDeviceCapability.MEASURE_DAILY_POWER, EDeviceCapability.MEASURE_POWER,
        EDeviceCapability.MEASURE_FILTER_STATE, 
        EDeviceCapability.MEASURE_PARTICLES,   
        EDeviceCapability.PURIFIER_MODE        
    },
    EDeviceType.AIR_PURIFIER_L: {
        EDeviceCapability.ONOFF, EDeviceCapability.MEASURE_TEMPERATURE, EDeviceCapability.MEASURE_HUMIDITY,
        EDeviceCapability.CHILD_LOCK, EDeviceCapability.MEASURE_FILTER_STATE, EDeviceCapability.MEASURE_PARTICLES,
        EDeviceCapability.MEASURE_PM1, EDeviceCapability.MEASURE_PM25, EDeviceCapability.MEASURE_PM10,
        EDeviceCapability.MEASURE_CO2, EDeviceCapability.MEASURE_TVOC, EDeviceCapability.MEASURE_DAILY_POWER,
        EDeviceCapability.MEASURE_POWER,
        EDeviceCapability.PURIFIER_MODE 
    },
    EDeviceType.HEATPUMP: {
        EDeviceCapability.ONOFF, EDeviceCapability.MEASURE_TEMPERATURE, EDeviceCapability.MEASURE_TEMPERATURE_VIRTUAL,
        EDeviceCapability.TARGET_TEMPERATURE, EDeviceCapability.MEASURE_DAILY_POWER, EDeviceCapability.GREE_MODE,
        EDeviceCapability.GREE_FAN_SPEED_MODE, EDeviceCapability.GREE_FAN_SPEED, EDeviceCapability.GREE_SWEEPING_ANGLE_VERTICAL,
        EDeviceCapability.GREE_SWEEPING_ANGLE_HORIZONTAL, EDeviceCapability.GREE_DISPLAY_LIGHT
    },

    EDeviceType.OIL_HEATER_GEN3_V2: {
        EDeviceCapability.ONOFF, EDeviceCapability.TARGET_TEMPERATURE, EDeviceCapability.MEASURE_TEMPERATURE,
        EDeviceCapability.INDIVIDUAL_CONTROL, EDeviceCapability.CHILD_LOCK, EDeviceCapability.COMMERCIAL_LOCK,
        EDeviceCapability.OPEN_WINDOW, EDeviceCapability.PREDICTIVE_HEATING, EDeviceCapability.MEASURE_WATTAGE,
        EDeviceCapability.MEASURE_DAILY_POWER, EDeviceCapability.MEASURE_POWER
    },
    EDeviceType.PANEL_HEATER_GEN4: {
        EDeviceCapability.ONOFF, EDeviceCapability.TARGET_TEMPERATURE, EDeviceCapability.MEASURE_TEMPERATURE,
        EDeviceCapability.INDIVIDUAL_CONTROL, EDeviceCapability.CHILD_LOCK, EDeviceCapability.COMMERCIAL_LOCK,
        EDeviceCapability.OPEN_WINDOW, EDeviceCapability.PREDICTIVE_HEATING, EDeviceCapability.ADJUST_WATTAGE,
        EDeviceCapability.PID_CONTROLLER, EDeviceCapability.SLOW_PID, EDeviceCapability.MEASURE_DAILY_POWER,
        EDeviceCapability.MEASURE_POWER
    },
}
