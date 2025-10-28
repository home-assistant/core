"""Constants used in KNX config store."""

from typing import Final

# Common
CONF_DATA: Final = "data"
CONF_ENTITY: Final = "entity"
CONF_DEVICE_INFO: Final = "device_info"
CONF_GA_WRITE: Final = "write"
CONF_GA_STATE: Final = "state"
CONF_GA_PASSIVE: Final = "passive"
CONF_DPT: Final = "dpt"

CONF_GA_SENSOR: Final = "ga_sensor"
CONF_GA_SWITCH: Final = "ga_switch"

# Climate
CONF_GA_TEMPERATURE_CURRENT: Final = "ga_temperature_current"
CONF_GA_HUMIDITY_CURRENT: Final = "ga_humidity_current"
CONF_TARGET_TEMPERATURE: Final = "target_temperature"
CONF_GA_TEMPERATURE_TARGET: Final = "ga_temperature_target"
CONF_GA_SETPOINT_SHIFT: Final = "ga_setpoint_shift"
CONF_GA_ACTIVE: Final = "ga_active"
CONF_GA_VALVE: Final = "ga_valve"
CONF_GA_OPERATION_MODE: Final = "ga_operation_mode"
CONF_IGNORE_AUTO_MODE: Final = "ignore_auto_mode"
CONF_GA_OP_MODE_COMFORT: Final = "ga_operation_mode_comfort"
CONF_GA_OP_MODE_ECO: Final = "ga_operation_mode_economy"
CONF_GA_OP_MODE_STANDBY: Final = "ga_operation_mode_standby"
CONF_GA_OP_MODE_PROTECTION: Final = "ga_operation_mode_protection"
CONF_GA_HEAT_COOL: Final = "ga_heat_cool"
CONF_GA_ON_OFF: Final = "ga_on_off"
CONF_GA_CONTROLLER_MODE: Final = "ga_controller_mode"
CONF_GA_CONTROLLER_STATUS: Final = "ga_controller_status"
CONF_GA_FAN_SPEED: Final = "ga_fan_speed"
CONF_GA_FAN_SWING: Final = "ga_fan_swing"
CONF_GA_FAN_SWING_HORIZONTAL: Final = "ga_fan_swing_horizontal"

# Cover
CONF_GA_UP_DOWN: Final = "ga_up_down"
CONF_GA_STOP: Final = "ga_stop"
CONF_GA_STEP: Final = "ga_step"
CONF_GA_POSITION_SET: Final = "ga_position_set"
CONF_GA_POSITION_STATE: Final = "ga_position_state"
CONF_GA_ANGLE: Final = "ga_angle"

# Light
CONF_COLOR_TEMP_MIN: Final = "color_temp_min"
CONF_COLOR_TEMP_MAX: Final = "color_temp_max"
CONF_GA_BRIGHTNESS: Final = "ga_brightness"
CONF_GA_COLOR_TEMP: Final = "ga_color_temp"
# Light/color
CONF_COLOR: Final = "color"
CONF_GA_COLOR: Final = "ga_color"
CONF_GA_RED_BRIGHTNESS: Final = "ga_red_brightness"
CONF_GA_RED_SWITCH: Final = "ga_red_switch"
CONF_GA_GREEN_BRIGHTNESS: Final = "ga_green_brightness"
CONF_GA_GREEN_SWITCH: Final = "ga_green_switch"
CONF_GA_BLUE_BRIGHTNESS: Final = "ga_blue_brightness"
CONF_GA_BLUE_SWITCH: Final = "ga_blue_switch"
CONF_GA_WHITE_BRIGHTNESS: Final = "ga_white_brightness"
CONF_GA_WHITE_SWITCH: Final = "ga_white_switch"
CONF_GA_HUE: Final = "ga_hue"
CONF_GA_SATURATION: Final = "ga_saturation"
