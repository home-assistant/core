"""Voluptuous schemas for the KNX integration."""

from __future__ import annotations

from abc import ABC
from collections import OrderedDict
from typing import ClassVar, Final

import voluptuous as vol
from xknx.devices.climate import SetpointShiftMode
from xknx.dpt import DPTBase, DPTNumeric
from xknx.exceptions import ConversionError, CouldNotParseTelegram

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.climate import HVACMode
from homeassistant.components.cover import (
    DEVICE_CLASSES_SCHEMA as COVER_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.number import NumberMode
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA as SENSOR_DEVICE_CLASSES_SCHEMA,
    STATE_CLASSES_SCHEMA,
)
from homeassistant.components.switch import (
    DEVICE_CLASSES_SCHEMA as SWITCH_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.text import TextMode
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_ENTITY_ID,
    CONF_EVENT,
    CONF_MODE,
    CONF_NAME,
    CONF_PAYLOAD,
    CONF_TYPE,
    CONF_VALUE_TEMPLATE,
    Platform,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ENTITY_CATEGORIES_SCHEMA

from .const import (
    CONF_INVERT,
    CONF_KNX_EXPOSE,
    CONF_PAYLOAD_LENGTH,
    CONF_RESET_AFTER,
    CONF_RESPOND_TO_READ,
    CONF_STATE_ADDRESS,
    CONF_SYNC_STATE,
    CONTROLLER_MODES,
    KNX_ADDRESS,
    PRESET_MODES,
    ColorTempModes,
)
from .validation import (
    ga_list_validator,
    ga_validator,
    numeric_type_validator,
    sensor_type_validator,
    string_type_validator,
    sync_state_validator,
)


##################
# KNX SUB VALIDATORS
##################
def number_limit_sub_validator(entity_config: OrderedDict) -> OrderedDict:
    """Validate a number entity configurations dependent on configured value type."""
    value_type = entity_config[CONF_TYPE]
    min_config: float | None = entity_config.get(NumberSchema.CONF_MIN)
    max_config: float | None = entity_config.get(NumberSchema.CONF_MAX)
    step_config: float | None = entity_config.get(NumberSchema.CONF_STEP)
    dpt_class = DPTNumeric.parse_transcoder(value_type)

    if dpt_class is None:
        raise vol.Invalid(f"'type: {value_type}' is not a valid numeric sensor type.")
    # Infinity is not supported by Home Assistant frontend so user defined
    # config is required if if xknx DPTNumeric subclass defines it as limit.
    if min_config is None and dpt_class.value_min == float("-inf"):
        raise vol.Invalid(f"'min' key required for value type '{value_type}'")
    if min_config is not None and min_config < dpt_class.value_min:
        raise vol.Invalid(
            f"'min: {min_config}' undercuts possible minimum"
            f" of value type '{value_type}': {dpt_class.value_min}"
        )

    if max_config is None and dpt_class.value_max == float("inf"):
        raise vol.Invalid(f"'max' key required for value type '{value_type}'")
    if max_config is not None and max_config > dpt_class.value_max:
        raise vol.Invalid(
            f"'max: {max_config}' exceeds possible maximum"
            f" of value type '{value_type}': {dpt_class.value_max}"
        )

    if step_config is not None and step_config < dpt_class.resolution:
        raise vol.Invalid(
            f"'step: {step_config}' undercuts possible minimum step"
            f" of value type '{value_type}': {dpt_class.resolution}"
        )

    return entity_config


def _max_payload_value(payload_length: int) -> int:
    if payload_length == 0:
        return 0x3F
    return int(256**payload_length) - 1


def button_payload_sub_validator(entity_config: OrderedDict) -> OrderedDict:
    """Validate a button entity payload configuration."""
    if _type := entity_config.get(CONF_TYPE):
        _payload = entity_config[ButtonSchema.CONF_VALUE]
        if (transcoder := DPTBase.parse_transcoder(_type)) is None:
            raise vol.Invalid(f"'type: {_type}' is not a valid sensor type.")
        entity_config[CONF_PAYLOAD_LENGTH] = transcoder.payload_length
        try:
            _dpt_payload = transcoder.to_knx(_payload)
            _raw_payload = transcoder.validate_payload(_dpt_payload)
        except (ConversionError, CouldNotParseTelegram) as ex:
            raise vol.Invalid(
                f"'payload: {_payload}' not valid for 'type: {_type}'"
            ) from ex
        entity_config[CONF_PAYLOAD] = int.from_bytes(_raw_payload, byteorder="big")
        return entity_config

    _payload = entity_config[CONF_PAYLOAD]
    _payload_length = entity_config[CONF_PAYLOAD_LENGTH]
    if _payload > (max_payload := _max_payload_value(_payload_length)):
        raise vol.Invalid(
            f"'payload: {_payload}' exceeds possible maximum for "
            f"payload_length {_payload_length}: {max_payload}"
        )
    return entity_config


def select_options_sub_validator(entity_config: OrderedDict) -> OrderedDict:
    """Validate a select entity options configuration."""
    options_seen = set()
    payloads_seen = set()
    payload_length = entity_config[CONF_PAYLOAD_LENGTH]

    for opt in entity_config[SelectSchema.CONF_OPTIONS]:
        option = opt[SelectSchema.CONF_OPTION]
        payload = opt[CONF_PAYLOAD]
        if payload > (max_payload := _max_payload_value(payload_length)):
            raise vol.Invalid(
                f"'payload: {payload}' for 'option: {option}' exceeds possible"
                f" maximum of 'payload_length: {payload_length}': {max_payload}"
            )
        if option in options_seen:
            raise vol.Invalid(f"duplicate item for 'option' not allowed: {option}")
        options_seen.add(option)
        if payload in payloads_seen:
            raise vol.Invalid(f"duplicate item for 'payload' not allowed: {payload}")
        payloads_seen.add(payload)
    return entity_config


#########
# EVENT
#########


class EventSchema:
    """Voluptuous schema for KNX events."""

    KNX_EVENT_FILTER_SCHEMA = vol.Schema(
        {
            vol.Required(KNX_ADDRESS): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_TYPE): sensor_type_validator,
        }
    )

    SCHEMA = {
        vol.Optional(CONF_EVENT, default=[]): vol.All(
            cv.ensure_list, [KNX_EVENT_FILTER_SCHEMA]
        )
    }


#############
# PLATFORMS
#############


class KNXPlatformSchema(ABC):
    """Voluptuous schema for KNX platform entity configuration."""

    PLATFORM: ClassVar[Platform | str]
    ENTITY_SCHEMA: ClassVar[vol.Schema | vol.All | vol.Any]

    @classmethod
    def platform_node(cls) -> dict[vol.Optional, vol.All]:
        """Return a schema node for the platform."""
        return {
            vol.Optional(str(cls.PLATFORM)): vol.All(
                cv.ensure_list, [cls.ENTITY_SCHEMA]
            )
        }


class BinarySensorSchema(KNXPlatformSchema):
    """Voluptuous schema for KNX binary sensors."""

    PLATFORM = Platform.BINARY_SENSOR

    CONF_STATE_ADDRESS = CONF_STATE_ADDRESS
    CONF_SYNC_STATE = CONF_SYNC_STATE
    CONF_INVERT = CONF_INVERT
    CONF_IGNORE_INTERNAL_STATE = "ignore_internal_state"
    CONF_CONTEXT_TIMEOUT = "context_timeout"
    CONF_RESET_AFTER = CONF_RESET_AFTER

    DEFAULT_NAME = "KNX Binary Sensor"

    ENTITY_SCHEMA = vol.All(
        # deprecated since September 2020
        cv.deprecated("significant_bit"),
        cv.deprecated("automation"),
        vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
                vol.Optional(CONF_IGNORE_INTERNAL_STATE, default=False): cv.boolean,
                vol.Optional(CONF_INVERT, default=False): cv.boolean,
                vol.Required(CONF_STATE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_CONTEXT_TIMEOUT): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=10)
                ),
                vol.Optional(CONF_DEVICE_CLASS): BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
                vol.Optional(CONF_RESET_AFTER): cv.positive_float,
                vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
            }
        ),
    )


class ButtonSchema(KNXPlatformSchema):
    """Voluptuous schema for KNX buttons."""

    PLATFORM = Platform.BUTTON

    CONF_VALUE = "value"
    DEFAULT_NAME = "KNX Button"

    payload_or_value_msg = f"Please use only one of `{CONF_PAYLOAD}` or `{CONF_VALUE}`"
    length_or_type_msg = (
        f"Please use only one of `{CONF_PAYLOAD_LENGTH}` or `{CONF_TYPE}`"
    )

    ENTITY_SCHEMA = vol.All(
        vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Required(KNX_ADDRESS): ga_validator,
                vol.Exclusive(
                    CONF_PAYLOAD, "payload_or_value", msg=payload_or_value_msg
                ): object,
                vol.Exclusive(
                    CONF_VALUE, "payload_or_value", msg=payload_or_value_msg
                ): object,
                vol.Exclusive(
                    CONF_PAYLOAD_LENGTH, "length_or_type", msg=length_or_type_msg
                ): object,
                vol.Exclusive(
                    CONF_TYPE, "length_or_type", msg=length_or_type_msg
                ): object,
                vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
            }
        ),
        vol.Any(
            vol.Schema(
                # encoded value
                {
                    vol.Required(CONF_VALUE): vol.Any(int, float, str),
                    vol.Required(CONF_TYPE): sensor_type_validator,
                },
                extra=vol.ALLOW_EXTRA,
            ),
            vol.Schema(
                # raw payload - default is DPT 1 style True
                {
                    vol.Optional(CONF_PAYLOAD, default=1): cv.positive_int,
                    vol.Optional(CONF_PAYLOAD_LENGTH, default=0): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=14)
                    ),
                    vol.Optional(CONF_VALUE): None,
                    vol.Optional(CONF_TYPE): None,
                },
                extra=vol.ALLOW_EXTRA,
            ),
        ),
        # calculate raw CONF_PAYLOAD and CONF_PAYLOAD_LENGTH
        # from CONF_VALUE and CONF_TYPE if given and check payload size
        button_payload_sub_validator,
    )


class ClimateSchema(KNXPlatformSchema):
    """Voluptuous schema for KNX climate devices."""

    PLATFORM = Platform.CLIMATE

    CONF_ACTIVE_STATE_ADDRESS = "active_state_address"
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
    CONF_COMMAND_VALUE_STATE_ADDRESS = "command_value_state_address"
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
    CONF_DEFAULT_CONTROLLER_MODE = "default_controller_mode"
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

    ENTITY_SCHEMA = vol.All(
        # deprecated since September 2020
        cv.deprecated("setpoint_shift_step", replacement_key=CONF_TEMPERATURE_STEP),
        # deprecated since 2021.6
        cv.deprecated("create_temperature_sensors"),
        vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(
                    CONF_SETPOINT_SHIFT_MAX, default=DEFAULT_SETPOINT_SHIFT_MAX
                ): vol.All(int, vol.Range(min=0, max=32)),
                vol.Optional(
                    CONF_SETPOINT_SHIFT_MIN, default=DEFAULT_SETPOINT_SHIFT_MIN
                ): vol.All(int, vol.Range(min=-32, max=0)),
                vol.Optional(
                    CONF_TEMPERATURE_STEP, default=DEFAULT_TEMPERATURE_STEP
                ): vol.All(float, vol.Range(min=0, max=2)),
                vol.Required(CONF_TEMPERATURE_ADDRESS): ga_list_validator,
                vol.Required(CONF_TARGET_TEMPERATURE_STATE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_TARGET_TEMPERATURE_ADDRESS): ga_list_validator,
                vol.Inclusive(
                    CONF_SETPOINT_SHIFT_ADDRESS,
                    "setpoint_shift",
                    msg=(
                        "'setpoint_shift_address' and 'setpoint_shift_state_address' "
                        "are required for setpoint_shift configuration"
                    ),
                ): ga_list_validator,
                vol.Inclusive(
                    CONF_SETPOINT_SHIFT_STATE_ADDRESS,
                    "setpoint_shift",
                    msg=(
                        "'setpoint_shift_address' and 'setpoint_shift_state_address' "
                        "are required for setpoint_shift configuration"
                    ),
                ): ga_list_validator,
                vol.Optional(CONF_SETPOINT_SHIFT_MODE): vol.Maybe(
                    vol.All(vol.Upper, cv.enum(SetpointShiftMode))
                ),
                vol.Optional(CONF_ACTIVE_STATE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_COMMAND_VALUE_STATE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_OPERATION_MODE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_OPERATION_MODE_STATE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_CONTROLLER_STATUS_ADDRESS): ga_list_validator,
                vol.Optional(CONF_CONTROLLER_STATUS_STATE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_CONTROLLER_MODE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_CONTROLLER_MODE_STATE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_HEAT_COOL_ADDRESS): ga_list_validator,
                vol.Optional(CONF_HEAT_COOL_STATE_ADDRESS): ga_list_validator,
                vol.Optional(
                    CONF_OPERATION_MODE_FROST_PROTECTION_ADDRESS
                ): ga_list_validator,
                vol.Optional(CONF_OPERATION_MODE_NIGHT_ADDRESS): ga_list_validator,
                vol.Optional(CONF_OPERATION_MODE_COMFORT_ADDRESS): ga_list_validator,
                vol.Optional(CONF_OPERATION_MODE_STANDBY_ADDRESS): ga_list_validator,
                vol.Optional(CONF_ON_OFF_ADDRESS): ga_list_validator,
                vol.Optional(CONF_ON_OFF_STATE_ADDRESS): ga_list_validator,
                vol.Optional(
                    CONF_ON_OFF_INVERT, default=DEFAULT_ON_OFF_INVERT
                ): cv.boolean,
                vol.Optional(CONF_OPERATION_MODES): vol.All(
                    cv.ensure_list, [vol.In(PRESET_MODES)]
                ),
                vol.Optional(CONF_CONTROLLER_MODES): vol.All(
                    cv.ensure_list, [vol.In(CONTROLLER_MODES)]
                ),
                vol.Optional(
                    CONF_DEFAULT_CONTROLLER_MODE, default=HVACMode.HEAT
                ): vol.Coerce(HVACMode),
                vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
                vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
                vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
            }
        ),
    )


class CoverSchema(KNXPlatformSchema):
    """Voluptuous schema for KNX covers."""

    PLATFORM = Platform.COVER

    CONF_MOVE_LONG_ADDRESS = "move_long_address"
    CONF_MOVE_SHORT_ADDRESS = "move_short_address"
    CONF_STOP_ADDRESS = "stop_address"
    CONF_POSITION_ADDRESS = "position_address"
    CONF_POSITION_STATE_ADDRESS = "position_state_address"
    CONF_ANGLE_ADDRESS = "angle_address"
    CONF_ANGLE_STATE_ADDRESS = "angle_state_address"
    CONF_TRAVELLING_TIME_DOWN = "travelling_time_down"
    CONF_TRAVELLING_TIME_UP = "travelling_time_up"
    CONF_INVERT_UPDOWN = "invert_updown"
    CONF_INVERT_POSITION = "invert_position"
    CONF_INVERT_ANGLE = "invert_angle"

    DEFAULT_TRAVEL_TIME = 25
    DEFAULT_NAME = "KNX Cover"

    ENTITY_SCHEMA = vol.All(
        vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_MOVE_LONG_ADDRESS): ga_list_validator,
                vol.Optional(CONF_MOVE_SHORT_ADDRESS): ga_list_validator,
                vol.Optional(CONF_STOP_ADDRESS): ga_list_validator,
                vol.Optional(CONF_POSITION_ADDRESS): ga_list_validator,
                vol.Optional(CONF_POSITION_STATE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_ANGLE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_ANGLE_STATE_ADDRESS): ga_list_validator,
                vol.Optional(
                    CONF_TRAVELLING_TIME_DOWN, default=DEFAULT_TRAVEL_TIME
                ): cv.positive_float,
                vol.Optional(
                    CONF_TRAVELLING_TIME_UP, default=DEFAULT_TRAVEL_TIME
                ): cv.positive_float,
                vol.Optional(CONF_INVERT_UPDOWN, default=False): cv.boolean,
                vol.Optional(CONF_INVERT_POSITION, default=False): cv.boolean,
                vol.Optional(CONF_INVERT_ANGLE, default=False): cv.boolean,
                vol.Optional(CONF_DEVICE_CLASS): COVER_DEVICE_CLASSES_SCHEMA,
                vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
            }
        ),
        vol.Any(
            vol.Schema(
                {vol.Required(CONF_MOVE_LONG_ADDRESS): object},
                extra=vol.ALLOW_EXTRA,
            ),
            vol.Schema(
                {vol.Required(CONF_POSITION_ADDRESS): object},
                extra=vol.ALLOW_EXTRA,
            ),
            msg=(
                f"At least one of '{CONF_MOVE_LONG_ADDRESS}' or"
                f" '{CONF_POSITION_ADDRESS}' is required."
            ),
        ),
    )


class DateSchema(KNXPlatformSchema):
    """Voluptuous schema for KNX date."""

    PLATFORM = Platform.DATE

    DEFAULT_NAME = "KNX Date"

    ENTITY_SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_RESPOND_TO_READ, default=False): cv.boolean,
            vol.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
            vol.Required(KNX_ADDRESS): ga_list_validator,
            vol.Optional(CONF_STATE_ADDRESS): ga_list_validator,
            vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
        }
    )


class DateTimeSchema(KNXPlatformSchema):
    """Voluptuous schema for KNX date."""

    PLATFORM = Platform.DATETIME

    DEFAULT_NAME = "KNX DateTime"

    ENTITY_SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_RESPOND_TO_READ, default=False): cv.boolean,
            vol.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
            vol.Required(KNX_ADDRESS): ga_list_validator,
            vol.Optional(CONF_STATE_ADDRESS): ga_list_validator,
            vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
        }
    )


class ExposeSchema(KNXPlatformSchema):
    """Voluptuous schema for KNX exposures."""

    PLATFORM = CONF_KNX_EXPOSE

    CONF_KNX_EXPOSE_TYPE = CONF_TYPE
    CONF_KNX_EXPOSE_ATTRIBUTE = "attribute"
    CONF_KNX_EXPOSE_BINARY = "binary"
    CONF_KNX_EXPOSE_COOLDOWN = "cooldown"
    CONF_KNX_EXPOSE_DEFAULT = "default"
    EXPOSE_TIME_TYPES: Final = [
        "time",
        "date",
        "datetime",
    ]

    EXPOSE_TIME_SCHEMA = vol.Schema(
        {
            vol.Required(CONF_KNX_EXPOSE_TYPE): vol.All(
                cv.string, str.lower, vol.In(EXPOSE_TIME_TYPES)
            ),
            vol.Required(KNX_ADDRESS): ga_validator,
        }
    )
    EXPOSE_SENSOR_SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_KNX_EXPOSE_COOLDOWN, default=0): cv.positive_float,
            vol.Optional(CONF_RESPOND_TO_READ, default=True): cv.boolean,
            vol.Required(CONF_KNX_EXPOSE_TYPE): vol.Any(
                CONF_KNX_EXPOSE_BINARY, sensor_type_validator
            ),
            vol.Required(KNX_ADDRESS): ga_validator,
            vol.Required(CONF_ENTITY_ID): cv.entity_id,
            vol.Optional(CONF_KNX_EXPOSE_ATTRIBUTE): cv.string,
            vol.Optional(CONF_KNX_EXPOSE_DEFAULT): cv.match_all,
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        }
    )
    ENTITY_SCHEMA = vol.Any(EXPOSE_SENSOR_SCHEMA, EXPOSE_TIME_SCHEMA)


class FanSchema(KNXPlatformSchema):
    """Voluptuous schema for KNX fans."""

    PLATFORM = Platform.FAN

    CONF_STATE_ADDRESS = CONF_STATE_ADDRESS
    CONF_OSCILLATION_ADDRESS = "oscillation_address"
    CONF_OSCILLATION_STATE_ADDRESS = "oscillation_state_address"
    CONF_MAX_STEP = "max_step"

    DEFAULT_NAME = "KNX Fan"

    ENTITY_SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Required(KNX_ADDRESS): ga_list_validator,
            vol.Optional(CONF_STATE_ADDRESS): ga_list_validator,
            vol.Optional(CONF_OSCILLATION_ADDRESS): ga_list_validator,
            vol.Optional(CONF_OSCILLATION_STATE_ADDRESS): ga_list_validator,
            vol.Optional(CONF_MAX_STEP): cv.byte,
            vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
        }
    )


class LightSchema(KNXPlatformSchema):
    """Voluptuous schema for KNX lights."""

    PLATFORM = Platform.LIGHT

    CONF_STATE_ADDRESS = CONF_STATE_ADDRESS
    CONF_BRIGHTNESS_ADDRESS = "brightness_address"
    CONF_BRIGHTNESS_STATE_ADDRESS = "brightness_state_address"
    CONF_COLOR_ADDRESS = "color_address"
    CONF_COLOR_STATE_ADDRESS = "color_state_address"
    CONF_COLOR_TEMP_ADDRESS = "color_temperature_address"
    CONF_COLOR_TEMP_STATE_ADDRESS = "color_temperature_state_address"
    CONF_COLOR_TEMP_MODE = "color_temperature_mode"
    CONF_HUE_ADDRESS = "hue_address"
    CONF_HUE_STATE_ADDRESS = "hue_state_address"
    CONF_RGBW_ADDRESS = "rgbw_address"
    CONF_RGBW_STATE_ADDRESS = "rgbw_state_address"
    CONF_SATURATION_ADDRESS = "saturation_address"
    CONF_SATURATION_STATE_ADDRESS = "saturation_state_address"
    CONF_XYY_ADDRESS = "xyy_address"
    CONF_XYY_STATE_ADDRESS = "xyy_state_address"
    CONF_MIN_KELVIN = "min_kelvin"
    CONF_MAX_KELVIN = "max_kelvin"

    DEFAULT_NAME = "KNX Light"
    DEFAULT_COLOR_TEMP_MODE = "absolute"
    DEFAULT_MIN_KELVIN = 2700  # 370 mireds
    DEFAULT_MAX_KELVIN = 6000  # 166 mireds

    CONF_INDIVIDUAL_COLORS = "individual_colors"
    CONF_RED = "red"
    CONF_GREEN = "green"
    CONF_BLUE = "blue"
    CONF_WHITE = "white"

    _hs_color_inclusion_msg = (
        "'hue_address', 'saturation_address' and 'brightness_address'"
        " are required for hs_color configuration"
    )
    HS_COLOR_SCHEMA = {
        vol.Optional(CONF_HUE_ADDRESS): ga_list_validator,
        vol.Optional(CONF_HUE_STATE_ADDRESS): ga_list_validator,
        vol.Optional(CONF_SATURATION_ADDRESS): ga_list_validator,
        vol.Optional(CONF_SATURATION_STATE_ADDRESS): ga_list_validator,
    }

    INDIVIDUAL_COLOR_SCHEMA = vol.Schema(
        {
            vol.Optional(KNX_ADDRESS): ga_list_validator,
            vol.Optional(CONF_STATE_ADDRESS): ga_list_validator,
            vol.Required(CONF_BRIGHTNESS_ADDRESS): ga_list_validator,
            vol.Optional(CONF_BRIGHTNESS_STATE_ADDRESS): ga_list_validator,
        }
    )

    ENTITY_SCHEMA = vol.All(
        vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(KNX_ADDRESS): ga_list_validator,
                vol.Optional(CONF_STATE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_BRIGHTNESS_ADDRESS): ga_list_validator,
                vol.Optional(CONF_BRIGHTNESS_STATE_ADDRESS): ga_list_validator,
                vol.Exclusive(CONF_INDIVIDUAL_COLORS, "color"): {
                    vol.Inclusive(
                        CONF_RED,
                        "individual_colors",
                        msg=(
                            "'red', 'green' and 'blue' are required for individual"
                            " colors configuration"
                        ),
                    ): INDIVIDUAL_COLOR_SCHEMA,
                    vol.Inclusive(
                        CONF_GREEN,
                        "individual_colors",
                        msg=(
                            "'red', 'green' and 'blue' are required for individual"
                            " colors configuration"
                        ),
                    ): INDIVIDUAL_COLOR_SCHEMA,
                    vol.Inclusive(
                        CONF_BLUE,
                        "individual_colors",
                        msg=(
                            "'red', 'green' and 'blue' are required for individual"
                            " colors configuration"
                        ),
                    ): INDIVIDUAL_COLOR_SCHEMA,
                    vol.Optional(CONF_WHITE): INDIVIDUAL_COLOR_SCHEMA,
                },
                vol.Exclusive(CONF_COLOR_ADDRESS, "color"): ga_list_validator,
                vol.Optional(CONF_COLOR_STATE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_COLOR_TEMP_ADDRESS): ga_list_validator,
                vol.Optional(CONF_COLOR_TEMP_STATE_ADDRESS): ga_list_validator,
                vol.Optional(
                    CONF_COLOR_TEMP_MODE, default=DEFAULT_COLOR_TEMP_MODE
                ): vol.All(vol.Upper, cv.enum(ColorTempModes)),
                **HS_COLOR_SCHEMA,
                vol.Exclusive(CONF_RGBW_ADDRESS, "color"): ga_list_validator,
                vol.Optional(CONF_RGBW_STATE_ADDRESS): ga_list_validator,
                vol.Exclusive(CONF_XYY_ADDRESS, "color"): ga_list_validator,
                vol.Optional(CONF_XYY_STATE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_MIN_KELVIN, default=DEFAULT_MIN_KELVIN): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
                vol.Optional(CONF_MAX_KELVIN, default=DEFAULT_MAX_KELVIN): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
                vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
            }
        ),
        vol.Any(
            vol.Schema(
                {vol.Required(KNX_ADDRESS): object},
                extra=vol.ALLOW_EXTRA,
            ),
            vol.Schema(  # brightness addresses are required in INDIVIDUAL_COLOR_SCHEMA
                {vol.Required(CONF_INDIVIDUAL_COLORS): object},
                extra=vol.ALLOW_EXTRA,
            ),
            msg="either 'address' or 'individual_colors' is required",
        ),
        vol.Any(
            vol.Schema(  # 'brightness' is non-optional for hs-color
                {
                    vol.Inclusive(
                        CONF_BRIGHTNESS_ADDRESS, "hs_color", msg=_hs_color_inclusion_msg
                    ): object,
                    vol.Inclusive(
                        CONF_HUE_ADDRESS, "hs_color", msg=_hs_color_inclusion_msg
                    ): object,
                    vol.Inclusive(
                        CONF_SATURATION_ADDRESS, "hs_color", msg=_hs_color_inclusion_msg
                    ): object,
                },
                extra=vol.ALLOW_EXTRA,
            ),
            vol.Schema(  # hs-colors not used
                {
                    vol.Optional(CONF_HUE_ADDRESS): None,
                    vol.Optional(CONF_SATURATION_ADDRESS): None,
                },
                extra=vol.ALLOW_EXTRA,
            ),
            msg=_hs_color_inclusion_msg,
        ),
    )


class NotifySchema(KNXPlatformSchema):
    """Voluptuous schema for KNX notifications."""

    PLATFORM = Platform.NOTIFY

    DEFAULT_NAME = "KNX Notify"

    ENTITY_SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_TYPE, default="latin_1"): string_type_validator,
            vol.Required(KNX_ADDRESS): ga_validator,
            vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
        }
    )


class NumberSchema(KNXPlatformSchema):
    """Voluptuous schema for KNX numbers."""

    PLATFORM = Platform.NUMBER

    CONF_MAX = "max"
    CONF_MIN = "min"
    CONF_STEP = "step"
    DEFAULT_NAME = "KNX Number"

    ENTITY_SCHEMA = vol.All(
        vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_RESPOND_TO_READ, default=False): cv.boolean,
                vol.Optional(CONF_MODE, default=NumberMode.AUTO): vol.Coerce(
                    NumberMode
                ),
                vol.Required(CONF_TYPE): numeric_type_validator,
                vol.Required(KNX_ADDRESS): ga_list_validator,
                vol.Optional(CONF_STATE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_MAX): vol.Coerce(float),
                vol.Optional(CONF_MIN): vol.Coerce(float),
                vol.Optional(CONF_STEP): cv.positive_float,
                vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
            }
        ),
        number_limit_sub_validator,
    )


class SceneSchema(KNXPlatformSchema):
    """Voluptuous schema for KNX scenes."""

    PLATFORM = Platform.SCENE

    CONF_SCENE_NUMBER = "scene_number"

    DEFAULT_NAME = "KNX SCENE"
    ENTITY_SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Required(KNX_ADDRESS): ga_list_validator,
            vol.Required(CONF_SCENE_NUMBER): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=64)
            ),
            vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
        }
    )


class SelectSchema(KNXPlatformSchema):
    """Voluptuous schema for KNX selects."""

    PLATFORM = Platform.SELECT

    CONF_OPTION = "option"
    CONF_OPTIONS = "options"
    DEFAULT_NAME = "KNX Select"

    ENTITY_SCHEMA = vol.All(
        vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
                vol.Optional(CONF_RESPOND_TO_READ, default=False): cv.boolean,
                vol.Required(CONF_PAYLOAD_LENGTH): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=14)
                ),
                vol.Required(CONF_OPTIONS): [
                    {
                        vol.Required(CONF_OPTION): vol.Coerce(str),
                        vol.Required(CONF_PAYLOAD): cv.positive_int,
                    }
                ],
                vol.Required(KNX_ADDRESS): ga_list_validator,
                vol.Optional(CONF_STATE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
            }
        ),
        select_options_sub_validator,
    )


class SensorSchema(KNXPlatformSchema):
    """Voluptuous schema for KNX sensors."""

    PLATFORM = Platform.SENSOR

    CONF_ALWAYS_CALLBACK = "always_callback"
    CONF_STATE_ADDRESS = CONF_STATE_ADDRESS
    CONF_SYNC_STATE = CONF_SYNC_STATE
    DEFAULT_NAME = "KNX Sensor"

    ENTITY_SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
            vol.Optional(CONF_ALWAYS_CALLBACK, default=False): cv.boolean,
            vol.Optional(CONF_STATE_CLASS): STATE_CLASSES_SCHEMA,
            vol.Required(CONF_TYPE): sensor_type_validator,
            vol.Required(CONF_STATE_ADDRESS): ga_list_validator,
            vol.Optional(CONF_DEVICE_CLASS): SENSOR_DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
        }
    )


class SwitchSchema(KNXPlatformSchema):
    """Voluptuous schema for KNX switches."""

    PLATFORM = Platform.SWITCH

    CONF_INVERT = CONF_INVERT
    CONF_STATE_ADDRESS = CONF_STATE_ADDRESS

    DEFAULT_NAME = "KNX Switch"
    ENTITY_SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_INVERT, default=False): cv.boolean,
            vol.Optional(CONF_RESPOND_TO_READ, default=False): cv.boolean,
            vol.Required(KNX_ADDRESS): ga_list_validator,
            vol.Optional(CONF_STATE_ADDRESS): ga_list_validator,
            vol.Optional(CONF_DEVICE_CLASS): SWITCH_DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
        }
    )


class TextSchema(KNXPlatformSchema):
    """Voluptuous schema for KNX text."""

    PLATFORM = Platform.TEXT

    DEFAULT_NAME = "KNX Text"

    ENTITY_SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_RESPOND_TO_READ, default=False): cv.boolean,
            vol.Optional(CONF_TYPE, default="latin_1"): string_type_validator,
            vol.Optional(CONF_MODE, default=TextMode.TEXT): vol.Coerce(TextMode),
            vol.Required(KNX_ADDRESS): ga_list_validator,
            vol.Optional(CONF_STATE_ADDRESS): ga_list_validator,
            vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
        }
    )


class TimeSchema(KNXPlatformSchema):
    """Voluptuous schema for KNX time."""

    PLATFORM = Platform.TIME

    DEFAULT_NAME = "KNX Time"

    ENTITY_SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_RESPOND_TO_READ, default=False): cv.boolean,
            vol.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
            vol.Required(KNX_ADDRESS): ga_list_validator,
            vol.Optional(CONF_STATE_ADDRESS): ga_list_validator,
            vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
        }
    )


class WeatherSchema(KNXPlatformSchema):
    """Voluptuous schema for KNX weather station."""

    PLATFORM = Platform.WEATHER

    CONF_SYNC_STATE = CONF_SYNC_STATE
    CONF_KNX_TEMPERATURE_ADDRESS = "address_temperature"
    CONF_KNX_BRIGHTNESS_SOUTH_ADDRESS = "address_brightness_south"
    CONF_KNX_BRIGHTNESS_EAST_ADDRESS = "address_brightness_east"
    CONF_KNX_BRIGHTNESS_WEST_ADDRESS = "address_brightness_west"
    CONF_KNX_BRIGHTNESS_NORTH_ADDRESS = "address_brightness_north"
    CONF_KNX_WIND_SPEED_ADDRESS = "address_wind_speed"
    CONF_KNX_WIND_BEARING_ADDRESS = "address_wind_bearing"
    CONF_KNX_RAIN_ALARM_ADDRESS = "address_rain_alarm"
    CONF_KNX_FROST_ALARM_ADDRESS = "address_frost_alarm"
    CONF_KNX_WIND_ALARM_ADDRESS = "address_wind_alarm"
    CONF_KNX_DAY_NIGHT_ADDRESS = "address_day_night"
    CONF_KNX_AIR_PRESSURE_ADDRESS = "address_air_pressure"
    CONF_KNX_HUMIDITY_ADDRESS = "address_humidity"

    DEFAULT_NAME = "KNX Weather Station"

    ENTITY_SCHEMA = vol.All(
        # deprecated since 2021.6
        cv.deprecated("create_sensors"),
        vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
                vol.Required(CONF_KNX_TEMPERATURE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_KNX_BRIGHTNESS_SOUTH_ADDRESS): ga_list_validator,
                vol.Optional(CONF_KNX_BRIGHTNESS_EAST_ADDRESS): ga_list_validator,
                vol.Optional(CONF_KNX_BRIGHTNESS_WEST_ADDRESS): ga_list_validator,
                vol.Optional(CONF_KNX_BRIGHTNESS_NORTH_ADDRESS): ga_list_validator,
                vol.Optional(CONF_KNX_WIND_SPEED_ADDRESS): ga_list_validator,
                vol.Optional(CONF_KNX_WIND_BEARING_ADDRESS): ga_list_validator,
                vol.Optional(CONF_KNX_RAIN_ALARM_ADDRESS): ga_list_validator,
                vol.Optional(CONF_KNX_FROST_ALARM_ADDRESS): ga_list_validator,
                vol.Optional(CONF_KNX_WIND_ALARM_ADDRESS): ga_list_validator,
                vol.Optional(CONF_KNX_DAY_NIGHT_ADDRESS): ga_list_validator,
                vol.Optional(CONF_KNX_AIR_PRESSURE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_KNX_HUMIDITY_ADDRESS): ga_list_validator,
                vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
            }
        ),
    )
