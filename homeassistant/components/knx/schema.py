"""Voluptuous schemas for the KNX integration."""

from __future__ import annotations

from abc import ABC
from collections import OrderedDict
from collections.abc import Callable, Mapping
from functools import cache
from typing import (
    Any,
    ClassVar,
    Final,
    Protocol,
    Self,
    TypedDict,
    cast,
    runtime_checkable,
)

import voluptuous as vol
from voluptuous_serialize import UNSUPPORTED, convert as volConvert
from xknx.devices.climate import FanSpeedMode, SetpointShiftMode
from xknx.dpt import DPTBase, DPTNumeric
from xknx.dpt.dpt_20 import HVACControllerMode, HVACOperationMode
from xknx.exceptions import ConversionError, CouldNotParseAddress, CouldNotParseTelegram
from xknx.telegram.address import (
    GroupAddress as XKnxGroupAddress,
    parse_device_group_address,
)

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.climate import FAN_OFF, HVACMode
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
    EntityCategory,
    Platform,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ENTITY_CATEGORIES_SCHEMA
from homeassistant.helpers.typing import VolSchemaType

from .const import (
    CONF_CONTEXT_TIMEOUT,
    CONF_IGNORE_INTERNAL_STATE,
    CONF_INVERT,
    CONF_KNX_EXPOSE,
    CONF_PAYLOAD_LENGTH,
    CONF_RESET_AFTER,
    CONF_RESPOND_TO_READ,
    CONF_STATE_ADDRESS,
    CONF_SYNC_STATE,
    KNX_ADDRESS,
    ColorTempModes,
    FanZeroMode,
)
from .storage.const import (
    CONF_DEVICE_INFO,
    CONF_DPT,
    CONF_GA_PASSIVE,
    CONF_GA_STATE,
    CONF_GA_WRITE,
)
from .validation import (
    backwards_compatible_xknx_climate_enum_member,
    dpt_base_type_validator,
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
            vol.Optional(CONF_TYPE): dpt_base_type_validator,
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
    DEFAULT_NAME = "KNX Binary Sensor"

    ENTITY_SCHEMA = vol.All(
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
    CONF_FAN_SPEED_ADDRESS = "fan_speed_address"
    CONF_FAN_SPEED_STATE_ADDRESS = "fan_speed_state_address"
    CONF_FAN_MAX_STEP = "fan_max_step"
    CONF_FAN_SPEED_MODE = "fan_speed_mode"
    CONF_FAN_ZERO_MODE = "fan_zero_mode"
    CONF_HUMIDITY_STATE_ADDRESS = "humidity_state_address"
    CONF_SWING_ADDRESS = "swing_address"
    CONF_SWING_STATE_ADDRESS = "swing_state_address"
    CONF_SWING_HORIZONTAL_ADDRESS = "swing_horizontal_address"
    CONF_SWING_HORIZONTAL_STATE_ADDRESS = "swing_horizontal_state_address"

    DEFAULT_NAME = "KNX Climate"
    DEFAULT_SETPOINT_SHIFT_MODE = "DPT6010"
    DEFAULT_SETPOINT_SHIFT_MAX = 6
    DEFAULT_SETPOINT_SHIFT_MIN = -6
    DEFAULT_TEMPERATURE_STEP = 0.1
    DEFAULT_ON_OFF_INVERT = False
    DEFAULT_FAN_SPEED_MODE = "percent"

    ENTITY_SCHEMA = vol.All(
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
                    cv.ensure_list,
                    [backwards_compatible_xknx_climate_enum_member(HVACOperationMode)],
                ),
                vol.Optional(CONF_CONTROLLER_MODES): vol.All(
                    cv.ensure_list,
                    [backwards_compatible_xknx_climate_enum_member(HVACControllerMode)],
                ),
                vol.Optional(
                    CONF_DEFAULT_CONTROLLER_MODE, default=HVACMode.HEAT
                ): vol.Coerce(HVACMode),
                vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
                vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
                vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
                vol.Optional(CONF_FAN_SPEED_ADDRESS): ga_list_validator,
                vol.Optional(CONF_FAN_SPEED_STATE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_FAN_MAX_STEP, default=3): cv.byte,
                vol.Optional(
                    CONF_FAN_SPEED_MODE, default=DEFAULT_FAN_SPEED_MODE
                ): vol.All(vol.Upper, cv.enum(FanSpeedMode)),
                vol.Optional(CONF_FAN_ZERO_MODE, default=FAN_OFF): vol.Coerce(
                    FanZeroMode
                ),
                vol.Optional(CONF_SWING_ADDRESS): ga_list_validator,
                vol.Optional(CONF_SWING_STATE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_SWING_HORIZONTAL_ADDRESS): ga_list_validator,
                vol.Optional(CONF_SWING_HORIZONTAL_STATE_ADDRESS): ga_list_validator,
                vol.Optional(CONF_HUMIDITY_STATE_ADDRESS): ga_list_validator,
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
    CONF_TIME = "time"
    CONF_DATE = "date"
    CONF_DATETIME = "datetime"
    EXPOSE_TIME_TYPES: Final = [CONF_TIME, CONF_DATE, CONF_DATETIME]

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


# NEW


@runtime_checkable
class VolValidator(Protocol):
    """Protocol for a Voluptuous-compatible validator.

    This Protocol defines the structure for classes that perform validation
    of dictionaries against a predefined schema. Implementing classes must
    provide a `__call__` method that validates the input, processes it, and
    returns a cleaned or transformed version of the data.

    The primary purpose is to ensure that classes implementing this Protocol
    are compatible with the Voluptuous library, raising `vol.Invalid` for any
    validation errors.
    """

    def __call__(self, value: Any) -> Any:
        """Validate and process a dictionary based on the implemented schema.

        This method checks if the provided dictionary adheres to the expected
        schema rules. If validation is successful, it may also perform data
        transformations or cleaning before returning the result. In case of
        validation errors, a `vol.Invalid` exception is raised.

        Args:
            value (dict[str, Any]): The input dictionary to validate.

        Returns:
            dict[str, Any]: The validated and potentially transformed dictionary.

        Raises:
            vol.Invalid: If the input does not conform to the expected schema or
            contains invalid data.

        """


@runtime_checkable
class SerializableSchema(Protocol):
    """Protocol for serializing Voluptuous schema definitions.

    This Protocol defines a structure for classes that implement schema serialization.
    The `serialize` method allows the transformation of a Voluptuous schema definition
    into a JSON-serializable dictionary format. This is particularly useful for
    providing schema details to frontend applications or APIs for dynamic form generation.

    Any class implementing this Protocol must provide a `serialize` method that:
      - Processes the class (`cls`) and an instance (`value`) of the same type.
      - Handles nested or complex schema definitions using a customizable `convert` function.
      - Returns a dictionary representation of the schema that adheres to JSON serialization rules.
    """

    def get_schema(self) -> VolSchemaType:
        """Return the Voluptuous schema definition for the class."""

    @classmethod
    def serialize(cls, value: Self, convert: Callable[[Any], Any]) -> dict[str, Any]:
        """Serialize a Voluptuous schema definition into a JSON-compatible dictionary.

        This method transforms an instance of the schema into a dictionary format
        that is ready for use in frontend applications or APIs. The `convert` parameter
        allows recursive handling of nested schemas or custom elements that require
        special processing.

        Args:
            cls (type[Self]): The schema class calling this method. This ensures
                type consistency between the schema class and the provided instance.
            value (Self): An instance of the schema class, containing the schema
                definition and any associated data.
            convert (Callable[[Any], Any]): A function to process nested or custom
                schema elements recursively. This ensures compatibility with complex
                or deeply nested schema structures.

        Returns:
            dict[str, Any]: A dictionary representation of the schema,
            ready for JSON serialization and suitable for frontend consumption.

        Raises:
            vol.Invalid: If the schema definition or its associated data is invalid
            or does not meet the required constraints.

        """


class ConfigGroupSchema(SerializableSchema):
    """Data entry flow section."""

    class UIOptions(TypedDict, total=False):
        """Represents the configuration for a ConfigGroup in the UI."""

        collapsible: bool  # Indicates whether the section can be collapsed by the user.
        collapsed: bool  # Specifies whether the section is initially collapsed.

    UI_OPTIONS_SCHEMA: Final[vol.Schema] = vol.Schema(
        vol.All(
            {
                vol.Optional("collapsible", default=False): bool,
                vol.Optional("collapsed", default=False): bool,
            },
            lambda value: value
            if value["collapsible"] or not value["collapsed"]
            else (_ for _ in ()).throw(
                vol.Invalid("'collapsed' can only be True if 'collapsible' is True.")
            ),
        )
    )

    def __init__(self, schema: vol.Schema, ui_options: UIOptions | None = None) -> None:
        """Initialize."""
        self.schema = schema
        self.ui_options: ConfigGroupSchema.UIOptions = self.UI_OPTIONS_SCHEMA(
            ui_options or {}
        )

    def __call__(self, value: Any) -> Any:
        """Validate value against schema."""
        return self.schema(value)

    def get_schema(self) -> VolSchemaType:
        """Return the Voluptuous schema definition for the class."""
        return self.schema

    @classmethod
    def serialize(
        cls, value: ConfigGroupSchema, convert: Callable[[Any], Any]
    ) -> dict[str, Any]:
        """Convert Section schema into a dictionary representation."""

        result: dict[str, Any] = {
            "type": "config_group",
            "ui_options": {
                "collapsible": value.ui_options["collapsible"],
            },
            "properties": convert(value.schema),
        }

        # Only add collapsed state if collapsible is True
        if value.ui_options["collapsible"]:
            result["ui_options"]["collapsed"] = value.ui_options["collapsed"]
        return result


class GroupAddressSchema(SerializableSchema):
    """Voluptuous-compatible validator for a KNX group address."""

    def __init__(
        self, allow_none: bool = False, allow_internal_address: bool = True
    ) -> None:
        """Initialize."""
        self.allow_none = allow_none
        self.allow_internal_address = allow_internal_address

    def __call__(self, value: str | int | None) -> str | int | None:
        """Validate that the value is parsable as GroupAddress or InternalGroupAddress."""
        if self.allow_none and value is None:
            return value

        if not isinstance(value, (str, int)):
            raise vol.Invalid(
                f"'{value}' is not a valid KNX group address: Invalid type '{type(value).__name__}'"
            )
        try:
            if not self.allow_internal_address:
                XKnxGroupAddress(value)
            else:
                parse_device_group_address(value)

        except CouldNotParseAddress as exc:
            raise vol.Invalid(
                f"'{value}' is not a valid KNX group address: {exc.message}"
            ) from exc
        return value

    def get_schema(self) -> VolSchemaType:
        """Return the Voluptuous schema definition for the class."""
        return vol.Schema(None)

    @classmethod
    def serialize(
        cls,
        value: GroupAddressSchema,
        convert: Callable[[vol.Schema], Any],
    ) -> dict[str, Any]:
        """Convert GroupAddress schema into a dictionary representation."""
        return {
            "type": "group_address",
            "allow_none": value.allow_none,
            "allow_internal_address": value.allow_internal_address,
        }


class GroupAddressListSchema(SerializableSchema):
    """Voluptuous-compatible validator for a collection of KNX group addresses."""

    schema: vol.Schema

    def __init__(self, allow_internal_addresses: bool = True) -> None:
        """Initialize the group address collection."""
        self.allow_internal_addresses = allow_internal_addresses
        self.schema = self._build_schema()

    def __call__(self, value: Any) -> Any:
        """Validate the passed data."""
        return self.schema(value)

    def _build_schema(self) -> vol.Schema:
        """Create the schema based on configuration."""
        return vol.Schema(
            vol.Any(
                [
                    GroupAddressSchema(
                        allow_internal_address=self.allow_internal_addresses
                    )
                ],
                vol.All(  # Coerce `None` to an empty list if passive is allowed
                    vol.IsFalse(), vol.SetTo(list)
                ),
            )
        )

    def get_schema(self) -> VolSchemaType:
        """Return the Voluptuous schema definition for the class."""
        return self.schema

    @classmethod
    def serialize(
        cls, value: GroupAddressListSchema, convert: Callable[[Any], Any]
    ) -> dict[str, Any]:
        """Convert GroupAddressCollection schema into a dictionary representation."""
        return {
            "type": "group_address_list",
            "items": convert(
                GroupAddressSchema(
                    allow_internal_address=value.allow_internal_addresses
                )
            ),
        }


class SyncStateSchema(SerializableSchema):
    """Voluptuous-compatible validator for sync state selector."""

    schema: Final = vol.Any(
        vol.All(vol.Coerce(int), vol.Range(min=2, max=1440)),
        vol.Match(r"^(init|expire|every)( \d*)?$"),
        # Ensure that the value is a type boolean and not coerced to a boolean
        lambda v: v
        if isinstance(v, bool)
        else (_ for _ in ()).throw(vol.Invalid("Invalid value")),
    )

    def __call__(self, value: Any) -> Any:
        """Validate value against schema."""
        return self.schema(value)

    def get_schema(self) -> VolSchemaType:
        """Return the Voluptuous schema definition for the class."""
        return self.schema

    @classmethod
    def serialize(
        cls, value: SyncStateSchema, convert: Callable[[Any], Any]
    ) -> dict[str, Any]:
        """Convert SyncState schema into a dictionary representation."""
        return {"type": "sync_state"}


class DptUtils:
    """Utility class for working with KNX Datapoint Types (DPTs)."""

    @staticmethod
    def format_dpt(dpt: type[DPTBase]) -> str:
        """Generate a string representation of a DPT class.

        Args:
            dpt: A DPT class type.

        Returns:
            A formatted string representation of the DPT class, including both main
            and sub numbers (e.g., '1.002'). If the sub number is None, only the
            main number is included (e.g., '14').

        Raises:
            ValueError: If an invalid DPT class is provided

        """
        if not issubclass(dpt, DPTBase) or not dpt.has_distinct_dpt_numbers():
            raise ValueError("Invalid DPT class provided.")

        return (
            f"{dpt.dpt_main_number}.{dpt.dpt_sub_number:03}"
            if dpt.dpt_sub_number is not None
            else f"{dpt.dpt_main_number}"
        )

    @staticmethod
    @cache
    def derive_subtypes(*types: type[DPTBase]) -> tuple[type[DPTBase], ...]:
        """Extract all distinct DPT types derived from the given DPT classes.

        This function takes one or more DPT classes as input and recursively
        gathers all types that are derived from these classes.

        Args:
            types: One or more DPT classes to process.

        Returns:
            A tuple of all distinct DPTs found in the class tree of the provided classes.

        """
        return tuple(
            dpt
            for dpt_class in types
            for dpt in dpt_class.dpt_class_tree()
            if dpt.has_distinct_dpt_numbers()
        )


class GroupAddressConfigSchema(SerializableSchema):
    """Voluptuous-compatible validator for the group address config."""

    schema: vol.Schema

    def __init__(
        self,
        write: bool = True,
        state: bool = True,
        passive: bool = True,
        write_required: bool = False,
        state_required: bool = False,
        allowed_dpts: tuple[type[DPTBase], ...] | None = None,
    ) -> None:
        """Initialize the group address selector."""
        self.write = write
        self.state = state
        self.passive = passive
        self.write_required = write_required
        self.state_required = state_required
        self.allowed_dpts = allowed_dpts

        self.schema = self.build_schema()

    def __call__(self, data: Any) -> Any:
        """Validate the passed data."""
        return self.schema(data)

    def build_schema(self) -> vol.Schema:
        """Create the schema based on configuration."""
        schema: dict[vol.Marker, Any] = {}  # will be modified in-place
        self._add_group_addresses(schema)
        self._add_passive(schema)
        self._add_dpt(schema)
        return vol.Schema(schema)

    def _add_group_addresses(self, schema: dict[vol.Marker, Any]) -> None:
        """Add basic group address items to the schema."""

        items = [
            (CONF_GA_WRITE, self.write, self.write_required),
            (CONF_GA_STATE, self.state, self.state_required),
        ]

        for key, allowed, required in items:
            if not allowed:
                schema[vol.Remove(key)] = object
            elif required:
                schema[vol.Required(key)] = GroupAddressSchema()
            else:
                schema[
                    vol.Optional(
                        key,
                        default=None,
                    )
                ] = GroupAddressSchema(allow_none=True)

    def _add_passive(self, schema: dict[vol.Marker, Any]) -> None:
        """Add passive group addresses validator to the schema."""
        if self.passive:
            schema[
                vol.Optional(
                    CONF_GA_PASSIVE,
                    default=list,
                )
            ] = GroupAddressListSchema()
        else:
            schema[vol.Remove(CONF_GA_PASSIVE)] = object

    def _add_dpt(self, schema: dict[vol.Marker, Any]) -> None:
        """Add DPT validator to the schema."""
        if self.allowed_dpts is None:
            schema[vol.Remove(CONF_DPT)] = object
        else:
            schema[
                vol.Required(
                    CONF_DPT,
                )
            ] = vol.All(
                str,
                vol.In([DptUtils.format_dpt(dpt) for dpt in self.allowed_dpts]),
            )

    def get_schema(self) -> VolSchemaType:
        """Return the Voluptuous schema definition for the class."""
        return self.schema

    @classmethod
    def serialize(
        cls,
        value: GroupAddressConfigSchema,
        convert: Callable[[Any], Any],
    ) -> dict[str, Any]:
        """Convert GroupAddressConfig schema into a dictionary representation."""

        return {
            "type": "group_address_config",
            "properties": convert(value.build_schema()),
        }


class EntityConfigGroupSchema(ConfigGroupSchema):
    """Voluptuous-compatible validator for the entity configuration group."""

    def __init__(
        self, allowed_categories: tuple[EntityCategory, ...] | None = None
    ) -> None:
        """Initialize the schema with optional allowed categories.

        :param allowed_categories: Tuple of allowed EntityCategory values.
        """

        allowed_categories = allowed_categories or tuple(EntityCategory)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME,
                ): str,
                vol.Optional(
                    CONF_ENTITY_CATEGORY,
                    default=None,
                ): vol.Maybe(vol.In(allowed_categories)),
                vol.Optional(
                    CONF_DEVICE_INFO,
                    default=None,
                ): vol.Maybe(str),
            },
        )

        super().__init__(schema)


class PlatformConfigSchema(SerializableSchema):
    """Data entry flow section."""

    def __init__(
        self,
        platform: str,
        config_schema: vol.Schema,
    ) -> None:
        """Initialize."""
        self.schema = vol.Schema(
            {
                vol.Required("platform"): platform,
                vol.Required(
                    "config",
                ): ConfigGroupSchema(config_schema),
            }
        )

    def __call__(self, value: Any) -> dict[str, Any]:
        """Validate value against schema."""
        return cast(dict, self.schema(value))

    def get_schema(self) -> VolSchemaType:
        """Return the Voluptuous schema definition for the class."""
        return self.schema

    @classmethod
    def serialize(
        cls, value: PlatformConfigSchema, convert: Callable[[Any], Any]
    ) -> dict[str, Any]:
        """Convert Section schema into a dictionary representation."""

        return {
            "type": "platform_config",
            "properties": convert(value.schema),
        }


class SchemaSerializer:
    """A utility class to serialize different KNX-related object types (e.g., GASelector or Section)."""

    _supported_types: tuple[type[SerializableSchema], ...] = (
        ConfigGroupSchema,
        GroupAddressConfigSchema,
        GroupAddressListSchema,
        GroupAddressSchema,
        PlatformConfigSchema,
        SyncStateSchema,
    )

    @classmethod
    def convert(cls, schema: Any) -> Any:
        """Convert a Voluptuous schema into a dictionary representation.

        This method utilizes a custom serializer to transform the given
        Voluptuous schema into a structured dictionary format.

        Args:
            schema (Any): A Voluptuous schema object to be converted.

        Returns:
            Any: A dictionary representing the converted schema.

        Raises:
            TypeError: If the input schema is not a valid Voluptuous schema.

        """
        return volConvert(schema, custom_serializer=cls._serializer)

    @classmethod
    def _serializer(cls, value: Any) -> Any | object:
        """Determine how to serialize the given object based on its type.

        - If `value` is an instance of one of the types in `_supported_types`,
            the corresponding `serialize` method is called.
        - If `value` is a Mapping (e.g., a dictionary), it iterates over
            its items and creates a serialized list of key-value pairs.
        - If the type is not supported, `UNSUPPORTED` is returned.

        Args:
            value (Any): The object to be serialized (e.g., GASelector, Section, etc.).

        Returns:
            Any | object: A dictionary or list representing the serialized object.
                            Returns `UNSUPPORTED` if the type is not supported.

        Raises:
            TypeError: If the serialization process encounters an unexpected type.

        """
        # Check if `value` matches one of the supported types
        for supported_type in cls._supported_types:
            if isinstance(value, supported_type):
                # Call the appropriate serialize method
                return supported_type.serialize(value, cls.convert)

        # If `value` is a Mapping (e.g., a dictionary), handle its items
        if isinstance(value, Mapping):
            serialized_items = []

            for key, child_value in value.items():
                # Skip entries if the key is of type vol.Remove
                if isinstance(key, vol.Remove):
                    continue

                description = None

                # If the key is a vol.Marker, extract schema and description
                if isinstance(key, vol.Marker):
                    param_name = key.schema
                    description = key.description
                else:
                    param_name = key

                # Convert the child value using the `convert` method
                serialized_value = cls.convert(child_value)
                serialized_value["name"] = param_name

                # If there's a description, add it to the serialized output
                if description is not None:
                    serialized_value["description"] = description

                # Check if the key is Required or Optional
                if isinstance(key, (vol.Required, vol.Optional)):
                    key_type_name = key.__class__.__name__.lower()
                    serialized_value[key_type_name] = True

                    # If the default is defined and callable, call it
                    if key.default is not vol.UNDEFINED and callable(key.default):
                        serialized_value["default"] = key.default()

                serialized_items.append(serialized_value)

            return serialized_items

        # If no supported type or Mapping is found, return UNSUPPORTED
        return UNSUPPORTED
