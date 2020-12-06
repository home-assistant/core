"""Voluptuous schemas for the KNX integration."""
import voluptuous as vol
from xknx.devices.climate import SetpointShiftMode
from xknx.io import DEFAULT_MCAST_PORT

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_TYPE,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_INVERT,
    CONF_RESET_AFTER,
    CONF_STATE_ADDRESS,
    CONF_SYNC_STATE,
    CONTROLLER_MODES,
    PRESET_MODES,
    ColorTempModes,
)


class ConnectionSchema:
    """Voluptuous schema for KNX connection."""

    CONF_KNX_LOCAL_IP = "local_ip"

    TUNNELING_SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_PORT, default=DEFAULT_MCAST_PORT): cv.port,
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_KNX_LOCAL_IP): cv.string,
        }
    )

    ROUTING_SCHEMA = vol.Schema({vol.Optional(CONF_KNX_LOCAL_IP): cv.string})


class CoverSchema:
    """Voluptuous schema for KNX covers."""

    CONF_MOVE_LONG_ADDRESS = "move_long_address"
    CONF_MOVE_SHORT_ADDRESS = "move_short_address"
    CONF_STOP_ADDRESS = "stop_address"
    CONF_POSITION_ADDRESS = "position_address"
    CONF_POSITION_STATE_ADDRESS = "position_state_address"
    CONF_ANGLE_ADDRESS = "angle_address"
    CONF_ANGLE_STATE_ADDRESS = "angle_state_address"
    CONF_TRAVELLING_TIME_DOWN = "travelling_time_down"
    CONF_TRAVELLING_TIME_UP = "travelling_time_up"
    CONF_INVERT_POSITION = "invert_position"
    CONF_INVERT_ANGLE = "invert_angle"

    DEFAULT_TRAVEL_TIME = 25
    DEFAULT_NAME = "KNX Cover"

    SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_MOVE_LONG_ADDRESS): cv.string,
            vol.Optional(CONF_MOVE_SHORT_ADDRESS): cv.string,
            vol.Optional(CONF_STOP_ADDRESS): cv.string,
            vol.Optional(CONF_POSITION_ADDRESS): cv.string,
            vol.Optional(CONF_POSITION_STATE_ADDRESS): cv.string,
            vol.Optional(CONF_ANGLE_ADDRESS): cv.string,
            vol.Optional(CONF_ANGLE_STATE_ADDRESS): cv.string,
            vol.Optional(
                CONF_TRAVELLING_TIME_DOWN, default=DEFAULT_TRAVEL_TIME
            ): cv.positive_int,
            vol.Optional(
                CONF_TRAVELLING_TIME_UP, default=DEFAULT_TRAVEL_TIME
            ): cv.positive_int,
            vol.Optional(CONF_INVERT_POSITION, default=False): cv.boolean,
            vol.Optional(CONF_INVERT_ANGLE, default=False): cv.boolean,
            vol.Optional(CONF_DEVICE_CLASS): cv.string,
        }
    )


class BinarySensorSchema:
    """Voluptuous schema for KNX binary sensors."""

    CONF_STATE_ADDRESS = CONF_STATE_ADDRESS
    CONF_SYNC_STATE = CONF_SYNC_STATE
    CONF_INVERT = CONF_INVERT
    CONF_IGNORE_INTERNAL_STATE = "ignore_internal_state"
    CONF_CONTEXT_TIMEOUT = "context_timeout"
    CONF_RESET_AFTER = CONF_RESET_AFTER

    DEFAULT_NAME = "KNX Binary Sensor"

    SCHEMA = vol.All(
        cv.deprecated("significant_bit"),
        cv.deprecated("automation"),
        vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_SYNC_STATE, default=True): vol.Any(
                    vol.All(vol.Coerce(int), vol.Range(min=2, max=1440)),
                    cv.boolean,
                    cv.string,
                ),
                vol.Optional(CONF_IGNORE_INTERNAL_STATE, default=False): cv.boolean,
                vol.Required(CONF_STATE_ADDRESS): cv.string,
                vol.Optional(CONF_CONTEXT_TIMEOUT): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=10)
                ),
                vol.Optional(CONF_DEVICE_CLASS): cv.string,
                vol.Optional(CONF_INVERT): cv.boolean,
                vol.Optional(CONF_RESET_AFTER): cv.positive_int,
            }
        ),
    )


class LightSchema:
    """Voluptuous schema for KNX lights."""

    CONF_STATE_ADDRESS = CONF_STATE_ADDRESS
    CONF_BRIGHTNESS_ADDRESS = "brightness_address"
    CONF_BRIGHTNESS_STATE_ADDRESS = "brightness_state_address"
    CONF_COLOR_ADDRESS = "color_address"
    CONF_COLOR_STATE_ADDRESS = "color_state_address"
    CONF_COLOR_TEMP_ADDRESS = "color_temperature_address"
    CONF_COLOR_TEMP_STATE_ADDRESS = "color_temperature_state_address"
    CONF_COLOR_TEMP_MODE = "color_temperature_mode"
    CONF_RGBW_ADDRESS = "rgbw_address"
    CONF_RGBW_STATE_ADDRESS = "rgbw_state_address"
    CONF_MIN_KELVIN = "min_kelvin"
    CONF_MAX_KELVIN = "max_kelvin"

    DEFAULT_NAME = "KNX Light"
    DEFAULT_COLOR_TEMP_MODE = "absolute"
    DEFAULT_MIN_KELVIN = 2700  # 370 mireds
    DEFAULT_MAX_KELVIN = 6000  # 166 mireds

    SCHEMA = vol.Schema(
        {
            vol.Required(CONF_ADDRESS): cv.string,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_STATE_ADDRESS): cv.string,
            vol.Optional(CONF_BRIGHTNESS_ADDRESS): cv.string,
            vol.Optional(CONF_BRIGHTNESS_STATE_ADDRESS): cv.string,
            vol.Optional(CONF_COLOR_ADDRESS): cv.string,
            vol.Optional(CONF_COLOR_STATE_ADDRESS): cv.string,
            vol.Optional(CONF_COLOR_TEMP_ADDRESS): cv.string,
            vol.Optional(CONF_COLOR_TEMP_STATE_ADDRESS): cv.string,
            vol.Optional(
                CONF_COLOR_TEMP_MODE, default=DEFAULT_COLOR_TEMP_MODE
            ): cv.enum(ColorTempModes),
            vol.Optional(CONF_RGBW_ADDRESS): cv.string,
            vol.Optional(CONF_RGBW_STATE_ADDRESS): cv.string,
            vol.Optional(CONF_MIN_KELVIN, default=DEFAULT_MIN_KELVIN): vol.All(
                vol.Coerce(int), vol.Range(min=1)
            ),
            vol.Optional(CONF_MAX_KELVIN, default=DEFAULT_MAX_KELVIN): vol.All(
                vol.Coerce(int), vol.Range(min=1)
            ),
        }
    )


class ClimateSchema:
    """Voluptuous schema for KNX climate devices."""

    CONF_SETPOINT_SHIFT_ADDRESS = "setpoint_shift_address"
    CONF_SETPOINT_SHIFT_STATE_ADDRESS = "setpoint_shift_state_address"
    CONF_SETPOINT_SHIFT_MODE = "setpoint_shift_mode"
    CONF_SETPOINT_SHIFT_MAX = "setpoint_shift_max"
    CONF_SETPOINT_SHIFT_MIN = "setpoint_shift_min"
    CONF_TEMPERATURE_ADDRESS = "temperature_address"
    CONF_TEMPERATURE_STEP = "temperature_step"
    CONF_TARGET_TEMPERATURE_ADDRESS = "target_temperature_address"
    CONF_TARGET_TEMPERATURE_STATE_ADDRESS = "target_temperature_state_address"
    CONF_OPERATION_MODE_ADDRESS = "operation_mode_address"
    CONF_OPERATION_MODE_STATE_ADDRESS = "operation_mode_state_address"
    CONF_CONTROLLER_STATUS_ADDRESS = "controller_status_address"
    CONF_CONTROLLER_STATUS_STATE_ADDRESS = "controller_status_state_address"
    CONF_CONTROLLER_MODE_ADDRESS = "controller_mode_address"
    CONF_CONTROLLER_MODE_STATE_ADDRESS = "controller_mode_state_address"
    CONF_HEAT_COOL_ADDRESS = "heat_cool_address"
    CONF_HEAT_COOL_STATE_ADDRESS = "heat_cool_state_address"
    CONF_OPERATION_MODE_FROST_PROTECTION_ADDRESS = (
        "operation_mode_frost_protection_address"
    )
    CONF_OPERATION_MODE_NIGHT_ADDRESS = "operation_mode_night_address"
    CONF_OPERATION_MODE_COMFORT_ADDRESS = "operation_mode_comfort_address"
    CONF_OPERATION_MODE_STANDBY_ADDRESS = "operation_mode_standby_address"
    CONF_OPERATION_MODES = "operation_modes"
    CONF_CONTROLLER_MODES = "controller_modes"
    CONF_ON_OFF_ADDRESS = "on_off_address"
    CONF_ON_OFF_STATE_ADDRESS = "on_off_state_address"
    CONF_ON_OFF_INVERT = "on_off_invert"
    CONF_MIN_TEMP = "min_temp"
    CONF_MAX_TEMP = "max_temp"

    DEFAULT_NAME = "KNX Climate"
    DEFAULT_SETPOINT_SHIFT_MODE = "DPT6010"
    DEFAULT_SETPOINT_SHIFT_MAX = 6
    DEFAULT_SETPOINT_SHIFT_MIN = -6
    DEFAULT_TEMPERATURE_STEP = 0.1
    DEFAULT_ON_OFF_INVERT = False

    SCHEMA = vol.All(
        cv.deprecated("setpoint_shift_step", replacement_key=CONF_TEMPERATURE_STEP),
        vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(
                    CONF_SETPOINT_SHIFT_MODE, default=DEFAULT_SETPOINT_SHIFT_MODE
                ): cv.enum(SetpointShiftMode),
                vol.Optional(
                    CONF_SETPOINT_SHIFT_MAX, default=DEFAULT_SETPOINT_SHIFT_MAX
                ): vol.All(int, vol.Range(min=0, max=32)),
                vol.Optional(
                    CONF_SETPOINT_SHIFT_MIN, default=DEFAULT_SETPOINT_SHIFT_MIN
                ): vol.All(int, vol.Range(min=-32, max=0)),
                vol.Optional(
                    CONF_TEMPERATURE_STEP, default=DEFAULT_TEMPERATURE_STEP
                ): vol.All(float, vol.Range(min=0, max=2)),
                vol.Required(CONF_TEMPERATURE_ADDRESS): cv.string,
                vol.Required(CONF_TARGET_TEMPERATURE_STATE_ADDRESS): cv.string,
                vol.Optional(CONF_TARGET_TEMPERATURE_ADDRESS): cv.string,
                vol.Optional(CONF_SETPOINT_SHIFT_ADDRESS): cv.string,
                vol.Optional(CONF_SETPOINT_SHIFT_STATE_ADDRESS): cv.string,
                vol.Optional(CONF_OPERATION_MODE_ADDRESS): cv.string,
                vol.Optional(CONF_OPERATION_MODE_STATE_ADDRESS): cv.string,
                vol.Optional(CONF_CONTROLLER_STATUS_ADDRESS): cv.string,
                vol.Optional(CONF_CONTROLLER_STATUS_STATE_ADDRESS): cv.string,
                vol.Optional(CONF_CONTROLLER_MODE_ADDRESS): cv.string,
                vol.Optional(CONF_CONTROLLER_MODE_STATE_ADDRESS): cv.string,
                vol.Optional(CONF_HEAT_COOL_ADDRESS): cv.string,
                vol.Optional(CONF_HEAT_COOL_STATE_ADDRESS): cv.string,
                vol.Optional(CONF_OPERATION_MODE_FROST_PROTECTION_ADDRESS): cv.string,
                vol.Optional(CONF_OPERATION_MODE_NIGHT_ADDRESS): cv.string,
                vol.Optional(CONF_OPERATION_MODE_COMFORT_ADDRESS): cv.string,
                vol.Optional(CONF_OPERATION_MODE_STANDBY_ADDRESS): cv.string,
                vol.Optional(CONF_ON_OFF_ADDRESS): cv.string,
                vol.Optional(CONF_ON_OFF_STATE_ADDRESS): cv.string,
                vol.Optional(
                    CONF_ON_OFF_INVERT, default=DEFAULT_ON_OFF_INVERT
                ): cv.boolean,
                vol.Optional(CONF_OPERATION_MODES): vol.All(
                    cv.ensure_list, [vol.In({**PRESET_MODES})]
                ),
                vol.Optional(CONF_CONTROLLER_MODES): vol.All(
                    cv.ensure_list, [vol.In({**CONTROLLER_MODES})]
                ),
                vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
                vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
            }
        ),
    )


class SwitchSchema:
    """Voluptuous schema for KNX switches."""

    CONF_INVERT = CONF_INVERT
    CONF_STATE_ADDRESS = CONF_STATE_ADDRESS

    DEFAULT_NAME = "KNX Switch"
    SCHEMA = vol.Schema(
        {
            vol.Required(CONF_ADDRESS): cv.string,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_STATE_ADDRESS): cv.string,
            vol.Optional(CONF_INVERT): cv.boolean,
        }
    )


class ExposeSchema:
    """Voluptuous schema for KNX exposures."""

    CONF_KNX_EXPOSE_TYPE = CONF_TYPE
    CONF_KNX_EXPOSE_ATTRIBUTE = "attribute"
    CONF_KNX_EXPOSE_DEFAULT = "default"
    CONF_KNX_EXPOSE_ADDRESS = CONF_ADDRESS

    SCHEMA = vol.Schema(
        {
            vol.Required(CONF_KNX_EXPOSE_TYPE): vol.Any(int, float, str),
            vol.Optional(CONF_ENTITY_ID): cv.entity_id,
            vol.Optional(CONF_KNX_EXPOSE_ATTRIBUTE): cv.string,
            vol.Optional(CONF_KNX_EXPOSE_DEFAULT): cv.match_all,
            vol.Required(CONF_KNX_EXPOSE_ADDRESS): cv.string,
        }
    )


class NotifySchema:
    """Voluptuous schema for KNX notifications."""

    DEFAULT_NAME = "KNX Notify"

    SCHEMA = vol.Schema(
        {
            vol.Required(CONF_ADDRESS): cv.string,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        }
    )


class SensorSchema:
    """Voluptuous schema for KNX sensors."""

    CONF_ALWAYS_CALLBACK = "always_callback"
    CONF_STATE_ADDRESS = CONF_STATE_ADDRESS
    CONF_SYNC_STATE = CONF_SYNC_STATE
    DEFAULT_NAME = "KNX Sensor"

    SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_SYNC_STATE, default=True): vol.Any(
                vol.All(vol.Coerce(int), vol.Range(min=2, max=1440)),
                cv.boolean,
                cv.string,
            ),
            vol.Optional(CONF_ALWAYS_CALLBACK, default=False): cv.boolean,
            vol.Required(CONF_STATE_ADDRESS): cv.string,
            vol.Required(CONF_TYPE): vol.Any(int, float, str),
        }
    )


class SceneSchema:
    """Voluptuous schema for KNX scenes."""

    CONF_SCENE_NUMBER = "scene_number"

    DEFAULT_NAME = "KNX SCENE"
    SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Required(CONF_ADDRESS): cv.string,
            vol.Required(CONF_SCENE_NUMBER): cv.positive_int,
        }
    )


class WeatherSchema:
    """Voluptuous schema for KNX weather station."""

    CONF_SYNC_STATE = CONF_SYNC_STATE
    CONF_KNX_TEMPERATURE_ADDRESS = "address_temperature"
    CONF_KNX_BRIGHTNESS_SOUTH_ADDRESS = "address_brightness_south"
    CONF_KNX_BRIGHTNESS_EAST_ADDRESS = "address_brightness_east"
    CONF_KNX_BRIGHTNESS_WEST_ADDRESS = "address_brightness_west"
    CONF_KNX_BRIGHTNESS_NORTH_ADDRESS = "address_brightness_north"
    CONF_KNX_WIND_SPEED_ADDRESS = "address_wind_speed"
    CONF_KNX_RAIN_ALARM_ADDRESS = "address_rain_alarm"
    CONF_KNX_FROST_ALARM_ADDRESS = "address_frost_alarm"
    CONF_KNX_WIND_ALARM_ADDRESS = "address_wind_alarm"
    CONF_KNX_DAY_NIGHT_ADDRESS = "address_day_night"
    CONF_KNX_AIR_PRESSURE_ADDRESS = "address_air_pressure"
    CONF_KNX_HUMIDITY_ADDRESS = "address_humidity"
    CONF_KNX_EXPOSE_SENSORS = "expose_sensors"

    DEFAULT_NAME = "KNX Weather Station"

    SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_SYNC_STATE, default=True): vol.Any(
                vol.All(vol.Coerce(int), vol.Range(min=2, max=1440)),
                cv.boolean,
                cv.string,
            ),
            vol.Optional(CONF_KNX_EXPOSE_SENSORS, default=False): cv.boolean,
            vol.Required(CONF_KNX_TEMPERATURE_ADDRESS): cv.string,
            vol.Optional(CONF_KNX_BRIGHTNESS_SOUTH_ADDRESS): cv.string,
            vol.Optional(CONF_KNX_BRIGHTNESS_EAST_ADDRESS): cv.string,
            vol.Optional(CONF_KNX_BRIGHTNESS_WEST_ADDRESS): cv.string,
            vol.Optional(CONF_KNX_BRIGHTNESS_NORTH_ADDRESS): cv.string,
            vol.Optional(CONF_KNX_WIND_SPEED_ADDRESS): cv.string,
            vol.Optional(CONF_KNX_RAIN_ALARM_ADDRESS): cv.string,
            vol.Optional(CONF_KNX_FROST_ALARM_ADDRESS): cv.string,
            vol.Optional(CONF_KNX_WIND_ALARM_ADDRESS): cv.string,
            vol.Optional(CONF_KNX_DAY_NIGHT_ADDRESS): cv.string,
            vol.Optional(CONF_KNX_AIR_PRESSURE_ADDRESS): cv.string,
            vol.Optional(CONF_KNX_HUMIDITY_ADDRESS): cv.string,
        }
    )
