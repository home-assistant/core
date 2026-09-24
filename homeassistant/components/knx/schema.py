"""Probatio schemas for the KNX integration."""

from abc import ABC
from collections import OrderedDict
from datetime import timedelta
from typing import ClassVar, Final

import probatio
from xknx.devices.climate import FanSpeedMode, SetpointShiftMode
from xknx.dpt import DPTBase, DPTNumeric
from xknx.dpt.dpt_20 import HVACControllerMode, HVACOperationMode
from xknx.exceptions import ConversionError, CouldNotParseTelegram

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.climate import FAN_OFF, HVACMode
from homeassistant.components.cover import (
    DEVICE_CLASSES_SCHEMA as COVER_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.number import (
    DEVICE_CLASSES_SCHEMA as NUMBER_DEVICE_CLASSES_SCHEMA,
    NumberMode,
)
from homeassistant.components.sensor import (
    CONF_STATE_CLASS as CONF_SENSOR_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA as SENSOR_DEVICE_CLASSES_SCHEMA,
    STATE_CLASSES_SCHEMA,
)
from homeassistant.components.switch import (
    DEVICE_CLASSES_SCHEMA as SWITCH_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.text import TextMode
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_ENTITY_ID,
    CONF_EVENT,
    CONF_ID,
    CONF_MODE,
    CONF_NAME,
    CONF_PAYLOAD,
    CONF_TYPE,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    Platform,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.util import slugify

from .const import (
    CONF_CONTEXT_TIMEOUT,
    CONF_DEFAULT_ENTITY_ID,
    CONF_IGNORE_INTERNAL_STATE,
    CONF_INVERT,
    CONF_KNX_EXPOSE,
    CONF_PAYLOAD_LENGTH,
    CONF_RESET_AFTER,
    CONF_RESPOND_TO_READ,
    CONF_STATE_ADDRESS,
    CONF_SYNC_STATE,
    CONF_VALUE,
    KNX_ADDRESS,
    UI_DEVICE_ID_PREFIX,
    ClimateConf,
    ColorTempModes,
    CoverConf,
    FanConf,
    FanZeroMode,
    NumberConf,
    SceneConf,
    SelectConf,
)
from .dpt import get_supported_dpts
from .validation import (
    backwards_compatible_xknx_climate_enum_member,
    dpt_base_type_validator,
    entity_category_validator,
    ga_list_validator,
    ga_validator,
    numeric_type_validator,
    sensor_type_validator,
    string_type_validator,
    sync_state_no_false_validator,
    sync_state_validator,
    validate_number_attributes,
    validate_sensor_attributes,
)


##################
# KNX SUB VALIDATORS
##################
def _number_limit_sub_validator(config: dict) -> dict:
    """Validate min, max, and step values for a number entity."""
    transcoder = DPTNumeric.parse_transcoder(config[CONF_TYPE])
    assert transcoder is not None  # already checked by numeric_type_validator
    validate_number_attributes(
        transcoder,
        min_config=config.get(NumberConf.MIN),
        max_config=config.get(NumberConf.MAX),
        step_config=config.get(NumberConf.STEP),
        device_class=config.get(CONF_DEVICE_CLASS),
        unit_of_measurement=config.get(CONF_UNIT_OF_MEASUREMENT),
    )
    return config


def _max_payload_value(payload_length: int) -> int:
    if payload_length == 0:
        return 0x3F
    return int(256**payload_length) - 1


def button_payload_sub_validator(entity_config: OrderedDict) -> OrderedDict:
    """Validate a button entity payload configuration.

    Returns raw payload and length from value and type (DPT), if given.
    """
    if _type := entity_config.get(CONF_TYPE):
        _payload = entity_config[CONF_VALUE]
        if (transcoder := DPTBase.parse_transcoder(_type)) is None:
            raise probatio.Invalid(f"'type: {_type}' is not a valid sensor type.")
        entity_config[CONF_PAYLOAD_LENGTH] = transcoder.payload_length
        try:
            _dpt_payload = transcoder.to_knx(_payload)
            _raw_payload = transcoder.validate_payload(_dpt_payload)
        except (ConversionError, CouldNotParseTelegram) as ex:
            raise probatio.Invalid(
                f"'payload: {_payload}' not valid for 'type: {_type}'"
            ) from ex
        entity_config[CONF_PAYLOAD] = int.from_bytes(_raw_payload, byteorder="big")
        return entity_config

    _payload = entity_config[CONF_PAYLOAD]
    _payload_length = entity_config[CONF_PAYLOAD_LENGTH]
    if _payload > (max_payload := _max_payload_value(_payload_length)):
        raise probatio.Invalid(
            f"'payload: {_payload}' exceeds possible maximum for "
            f"payload_length {_payload_length}: {max_payload}"
        )
    return entity_config


def select_options_sub_validator(entity_config: OrderedDict) -> OrderedDict:
    """Validate a select entity options configuration."""
    options_seen = set()
    payloads_seen = set()
    payload_length = entity_config[CONF_PAYLOAD_LENGTH]

    for opt in entity_config[SelectConf.OPTIONS]:
        option = opt[SelectConf.OPTION]
        payload = opt[CONF_PAYLOAD]
        if payload > (max_payload := _max_payload_value(payload_length)):
            raise probatio.Invalid(
                f"'payload: {payload}' for 'option: {option}' exceeds possible"
                f" maximum of 'payload_length: {payload_length}': {max_payload}"
            )
        if option in options_seen:
            raise probatio.Invalid(f"duplicate item for 'option' not allowed: {option}")
        options_seen.add(option)
        if payload in payloads_seen:
            raise probatio.Invalid(
                f"duplicate item for 'payload' not allowed: {payload}"
            )
        payloads_seen.add(payload)
    return entity_config


def _sensor_attribute_sub_validator(config: dict) -> dict:
    """Validate state_class, device_class and unit compatibility."""
    transcoder: type[DPTBase] = DPTBase.parse_transcoder(  # type: ignore[assignment]
        config[CONF_TYPE]
    )
    dpt_metadata = get_supported_dpts()[transcoder.dpt_number_str()]
    validate_sensor_attributes(
        dpt_metadata,
        state_class=config.get(CONF_SENSOR_STATE_CLASS),
        device_class=config.get(CONF_DEVICE_CLASS),
        unit_of_measurement=config.get(CONF_UNIT_OF_MEASUREMENT),
    )
    return config


#########
# EVENT
#########


class EventSchema:
    """Probatio schema for KNX events."""

    KNX_EVENT_FILTER_SCHEMA = probatio.Schema(
        {
            probatio.Required(KNX_ADDRESS): probatio.All(cv.ensure_list, [cv.string]),
            probatio.Optional(CONF_TYPE): dpt_base_type_validator,
        }
    )

    SCHEMA = {
        probatio.Optional(CONF_EVENT, default=[]): probatio.All(
            cv.ensure_list, [KNX_EVENT_FILTER_SCHEMA]
        )
    }


#############
# PLATFORMS
#############


def _unique_id_duplicate_validator(entities: list[dict]) -> list[dict]:
    """Validate that user-defined unique_ids are unique within a platform.

    The same unique_id on different platforms is allowed - the entity registry
    scopes uniqueness per (entity domain, integration).
    """
    seen: set[str] = set()
    for entity in entities:
        if (unique_id := entity.get(CONF_UNIQUE_ID)) is None:
            continue
        if unique_id in seen:
            raise probatio.Invalid(f"duplicate 'unique_id' not allowed: {unique_id}")
        seen.add(unique_id)
    return entities


class KNXPlatformSchema(ABC):
    """Probatio schema for KNX platform entity configuration."""

    PLATFORM: ClassVar[Platform | str]
    ENTITY_SCHEMA: ClassVar[probatio.Schema | probatio.All | probatio.Any]

    @classmethod
    def platform_node(cls) -> dict[probatio.Optional, probatio.All]:
        """Return a schema node for the platform."""
        return {
            probatio.Optional(str(cls.PLATFORM)): probatio.All(
                cv.ensure_list, [cls.ENTITY_SCHEMA], _unique_id_duplicate_validator
            )
        }


def _device_id(value: str) -> str:
    """Normalize a YAML device id.

    A value matching the identifier of a device created in the UI (see
    `UI_DEVICE_ID_PREFIX`) is passed through verbatim, so it keeps linking to
    that device. Any other value is slugified so ids that only differ in
    case or whitespace resolve to the same device instead of silently
    creating a separate one.
    """
    value = value.strip()
    if value.startswith(UI_DEVICE_ID_PREFIX):
        return value
    return slugify(value)


def _entity_base_schema(platform: Platform) -> probatio.Schema:
    """Return a base schema for KNX entities."""
    return probatio.Schema(
        {
            probatio.Optional(CONF_NAME, default=""): cv.string,
            probatio.Optional(CONF_DEVICE): probatio.Schema(
                {
                    probatio.Required(CONF_ID): probatio.All(
                        cv.string, _device_id, probatio.Length(min=1)
                    ),
                    probatio.Optional(CONF_NAME): cv.string,
                }
            ),
            probatio.Optional(CONF_DEFAULT_ENTITY_ID): probatio.All(
                cv.entity_id, cv.entity_domain(platform)
            ),
            probatio.Optional(CONF_ENTITY_CATEGORY): entity_category_validator(
                platform
            ),
            probatio.Optional(CONF_UNIQUE_ID): probatio.All(
                cv.string, probatio.Length(min=1)
            ),
        }
    )


class BinarySensorSchema(KNXPlatformSchema):
    """Probatio schema for KNX binary sensors."""

    PLATFORM = Platform.BINARY_SENSOR

    ENTITY_SCHEMA = probatio.All(
        _entity_base_schema(PLATFORM).extend(
            {
                probatio.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
                probatio.Optional(
                    CONF_IGNORE_INTERNAL_STATE, default=False
                ): cv.boolean,
                probatio.Optional(CONF_INVERT, default=False): cv.boolean,
                probatio.Required(CONF_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_CONTEXT_TIMEOUT): probatio.All(
                    probatio.Coerce(float), probatio.Range(min=0, max=10)
                ),
                probatio.Optional(
                    CONF_DEVICE_CLASS
                ): BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
                probatio.Optional(CONF_RESET_AFTER): cv.positive_float,
            }
        ),
    )


class ButtonSchema(KNXPlatformSchema):
    """Probatio schema for KNX buttons."""

    PLATFORM = Platform.BUTTON

    payload_or_value_msg = f"Please use only one of `{CONF_PAYLOAD}` or `{CONF_VALUE}`"
    length_or_type_msg = (
        f"Please use only one of `{CONF_PAYLOAD_LENGTH}` or `{CONF_TYPE}`"
    )

    ENTITY_SCHEMA = probatio.All(
        _entity_base_schema(PLATFORM).extend(
            {
                probatio.Required(KNX_ADDRESS): ga_validator,
                probatio.Exclusive(
                    CONF_PAYLOAD, "payload_or_value", msg=payload_or_value_msg
                ): object,
                probatio.Exclusive(
                    CONF_VALUE, "payload_or_value", msg=payload_or_value_msg
                ): object,
                probatio.Exclusive(
                    CONF_PAYLOAD_LENGTH, "length_or_type", msg=length_or_type_msg
                ): object,
                probatio.Exclusive(
                    CONF_TYPE, "length_or_type", msg=length_or_type_msg
                ): object,
            }
        ),
        probatio.Any(
            probatio.Schema(
                # encoded value
                {
                    probatio.Required(CONF_VALUE): probatio.Any(int, float, str),
                    probatio.Required(CONF_TYPE): sensor_type_validator,
                },
                extra=probatio.ALLOW_EXTRA,
            ),
            probatio.Schema(
                # raw payload - default is DPT 1 style True
                {
                    probatio.Optional(CONF_PAYLOAD, default=1): cv.positive_int,
                    probatio.Optional(CONF_PAYLOAD_LENGTH, default=0): probatio.All(
                        probatio.Coerce(int), probatio.Range(min=0, max=14)
                    ),
                    probatio.Optional(CONF_VALUE): None,
                    probatio.Optional(CONF_TYPE): None,
                },
                extra=probatio.ALLOW_EXTRA,
            ),
        ),
        # calculate raw CONF_PAYLOAD and CONF_PAYLOAD_LENGTH
        # from CONF_VALUE and CONF_TYPE if given and check payload size
        button_payload_sub_validator,
    )


class ClimateSchema(KNXPlatformSchema):
    """Probatio schema for KNX climate devices."""

    PLATFORM = Platform.CLIMATE

    CONF_ACTIVE_STATE_ADDRESS = "active_state_address"
    CONF_SETPOINT_SHIFT_ADDRESS = "setpoint_shift_address"
    CONF_SETPOINT_SHIFT_STATE_ADDRESS = "setpoint_shift_state_address"
    CONF_SETPOINT_SHIFT_MODE = "setpoint_shift_mode"
    CONF_TEMPERATURE_ADDRESS = "temperature_address"
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
    CONF_ON_OFF_ADDRESS = "on_off_address"
    CONF_ON_OFF_STATE_ADDRESS = "on_off_state_address"
    CONF_FAN_SPEED_ADDRESS = "fan_speed_address"
    CONF_FAN_SPEED_STATE_ADDRESS = "fan_speed_state_address"
    CONF_HUMIDITY_STATE_ADDRESS = "humidity_state_address"
    CONF_SWING_ADDRESS = "swing_address"
    CONF_SWING_STATE_ADDRESS = "swing_state_address"
    CONF_SWING_HORIZONTAL_ADDRESS = "swing_horizontal_address"
    CONF_SWING_HORIZONTAL_STATE_ADDRESS = "swing_horizontal_state_address"

    DEFAULT_SETPOINT_SHIFT_MODE = "DPT6010"
    DEFAULT_SETPOINT_SHIFT_MAX = 6
    DEFAULT_SETPOINT_SHIFT_MIN = -6
    DEFAULT_TEMPERATURE_STEP = 0.1
    DEFAULT_ON_OFF_INVERT = False
    DEFAULT_FAN_SPEED_MODE = "percent"

    ENTITY_SCHEMA = probatio.All(
        _entity_base_schema(PLATFORM).extend(
            {
                probatio.Optional(
                    ClimateConf.SETPOINT_SHIFT_MAX, default=DEFAULT_SETPOINT_SHIFT_MAX
                ): probatio.All(int, probatio.Range(min=0, max=32)),
                probatio.Optional(
                    ClimateConf.SETPOINT_SHIFT_MIN, default=DEFAULT_SETPOINT_SHIFT_MIN
                ): probatio.All(int, probatio.Range(min=-32, max=0)),
                probatio.Optional(
                    ClimateConf.TEMPERATURE_STEP, default=DEFAULT_TEMPERATURE_STEP
                ): probatio.All(float, probatio.Range(min=0, max=2)),
                probatio.Required(CONF_TEMPERATURE_ADDRESS): ga_list_validator,
                probatio.Required(
                    CONF_TARGET_TEMPERATURE_STATE_ADDRESS
                ): ga_list_validator,
                probatio.Optional(CONF_TARGET_TEMPERATURE_ADDRESS): ga_list_validator,
                probatio.Inclusive(
                    CONF_SETPOINT_SHIFT_ADDRESS,
                    "setpoint_shift",
                    msg=(
                        "'setpoint_shift_address' and 'setpoint_shift_state_address' "
                        "are required for setpoint_shift configuration"
                    ),
                ): ga_list_validator,
                probatio.Inclusive(
                    CONF_SETPOINT_SHIFT_STATE_ADDRESS,
                    "setpoint_shift",
                    msg=(
                        "'setpoint_shift_address' and 'setpoint_shift_state_address' "
                        "are required for setpoint_shift configuration"
                    ),
                ): ga_list_validator,
                probatio.Optional(CONF_SETPOINT_SHIFT_MODE): probatio.Maybe(
                    probatio.All(probatio.Upper, cv.enum(SetpointShiftMode))
                ),
                probatio.Optional(CONF_ACTIVE_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_COMMAND_VALUE_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_OPERATION_MODE_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_OPERATION_MODE_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_CONTROLLER_STATUS_ADDRESS): ga_list_validator,
                probatio.Optional(
                    CONF_CONTROLLER_STATUS_STATE_ADDRESS
                ): ga_list_validator,
                probatio.Optional(CONF_CONTROLLER_MODE_ADDRESS): ga_list_validator,
                probatio.Optional(
                    CONF_CONTROLLER_MODE_STATE_ADDRESS
                ): ga_list_validator,
                probatio.Optional(CONF_HEAT_COOL_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_HEAT_COOL_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(
                    CONF_OPERATION_MODE_FROST_PROTECTION_ADDRESS
                ): ga_list_validator,
                probatio.Optional(CONF_OPERATION_MODE_NIGHT_ADDRESS): ga_list_validator,
                probatio.Optional(
                    CONF_OPERATION_MODE_COMFORT_ADDRESS
                ): ga_list_validator,
                probatio.Optional(
                    CONF_OPERATION_MODE_STANDBY_ADDRESS
                ): ga_list_validator,
                probatio.Optional(CONF_ON_OFF_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_ON_OFF_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(
                    ClimateConf.ON_OFF_INVERT, default=DEFAULT_ON_OFF_INVERT
                ): cv.boolean,
                probatio.Optional(ClimateConf.OPERATION_MODES): probatio.All(
                    cv.ensure_list,
                    [backwards_compatible_xknx_climate_enum_member(HVACOperationMode)],
                ),
                probatio.Optional(ClimateConf.CONTROLLER_MODES): probatio.All(
                    cv.ensure_list,
                    [backwards_compatible_xknx_climate_enum_member(HVACControllerMode)],
                ),
                probatio.Optional(
                    ClimateConf.DEFAULT_CONTROLLER_MODE, default=HVACMode.HEAT
                ): probatio.Coerce(HVACMode),
                probatio.Optional(ClimateConf.MIN_TEMP): probatio.Coerce(float),
                probatio.Optional(ClimateConf.MAX_TEMP): probatio.Coerce(float),
                probatio.Optional(CONF_FAN_SPEED_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_FAN_SPEED_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(ClimateConf.FAN_MAX_STEP, default=3): cv.byte,
                probatio.Optional(
                    ClimateConf.FAN_SPEED_MODE, default=DEFAULT_FAN_SPEED_MODE
                ): probatio.All(probatio.Upper, cv.enum(FanSpeedMode)),
                probatio.Optional(
                    ClimateConf.FAN_ZERO_MODE, default=FAN_OFF
                ): probatio.Coerce(FanZeroMode),
                probatio.Optional(CONF_SWING_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_SWING_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_SWING_HORIZONTAL_ADDRESS): ga_list_validator,
                probatio.Optional(
                    CONF_SWING_HORIZONTAL_STATE_ADDRESS
                ): ga_list_validator,
                probatio.Optional(CONF_HUMIDITY_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(
                    CONF_SYNC_STATE, default=True
                ): sync_state_no_false_validator,
            }
        ),
    )


class CoverSchema(KNXPlatformSchema):
    """Probatio schema for KNX covers."""

    PLATFORM = Platform.COVER

    CONF_MOVE_LONG_ADDRESS = "move_long_address"
    CONF_MOVE_SHORT_ADDRESS = "move_short_address"
    CONF_STOP_ADDRESS = "stop_address"
    CONF_POSITION_ADDRESS = "position_address"
    CONF_POSITION_STATE_ADDRESS = "position_state_address"
    CONF_ANGLE_ADDRESS = "angle_address"
    CONF_ANGLE_STATE_ADDRESS = "angle_state_address"

    DEFAULT_TRAVEL_TIME = 25

    ENTITY_SCHEMA = probatio.All(
        _entity_base_schema(PLATFORM).extend(
            {
                probatio.Optional(CONF_MOVE_LONG_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_MOVE_SHORT_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_STOP_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_POSITION_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_POSITION_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_ANGLE_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_ANGLE_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(
                    CoverConf.TRAVELLING_TIME_DOWN, default=DEFAULT_TRAVEL_TIME
                ): cv.positive_float,
                probatio.Optional(
                    CoverConf.TRAVELLING_TIME_UP, default=DEFAULT_TRAVEL_TIME
                ): cv.positive_float,
                probatio.Optional(CoverConf.INVERT_UPDOWN, default=False): cv.boolean,
                probatio.Optional(CoverConf.INVERT_POSITION, default=False): cv.boolean,
                probatio.Optional(CoverConf.INVERT_ANGLE, default=False): cv.boolean,
                probatio.Optional(CONF_DEVICE_CLASS): COVER_DEVICE_CLASSES_SCHEMA,
                probatio.Optional(
                    CONF_SYNC_STATE, default=True
                ): sync_state_no_false_validator,
            }
        ),
        probatio.Any(
            probatio.Schema(
                {probatio.Required(CONF_MOVE_LONG_ADDRESS): object},
                extra=probatio.ALLOW_EXTRA,
            ),
            probatio.Schema(
                {probatio.Required(CONF_POSITION_ADDRESS): object},
                extra=probatio.ALLOW_EXTRA,
            ),
            msg=(
                f"At least one of '{CONF_MOVE_LONG_ADDRESS}' or"
                f" '{CONF_POSITION_ADDRESS}' is required."
            ),
        ),
    )


class DateSchema(KNXPlatformSchema):
    """Probatio schema for KNX date."""

    PLATFORM = Platform.DATE

    ENTITY_SCHEMA = _entity_base_schema(PLATFORM).extend(
        {
            probatio.Optional(CONF_RESPOND_TO_READ, default=False): cv.boolean,
            probatio.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
            probatio.Required(KNX_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_STATE_ADDRESS): ga_list_validator,
        }
    )


class DateTimeSchema(KNXPlatformSchema):
    """Probatio schema for KNX date."""

    PLATFORM = Platform.DATETIME

    ENTITY_SCHEMA = _entity_base_schema(PLATFORM).extend(
        {
            probatio.Optional(CONF_RESPOND_TO_READ, default=False): cv.boolean,
            probatio.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
            probatio.Required(KNX_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_STATE_ADDRESS): ga_list_validator,
        }
    )


class ExposeSchema(KNXPlatformSchema):
    """Probatio schema for KNX exposures."""

    PLATFORM = CONF_KNX_EXPOSE

    CONF_KNX_EXPOSE_TYPE = CONF_TYPE
    CONF_KNX_EXPOSE_ATTRIBUTE = "attribute"
    CONF_KNX_EXPOSE_BINARY = "binary"
    CONF_KNX_EXPOSE_COOLDOWN = "cooldown"
    CONF_KNX_EXPOSE_SEND_ON_INIT = "send_on_init"
    CONF_KNX_EXPOSE_PERIODIC_SEND = "periodic_send"
    CONF_KNX_EXPOSE_DEFAULT = "default"
    CONF_TIME = "time"
    CONF_DATE = "date"
    CONF_DATETIME = "datetime"
    EXPOSE_TIME_TYPES: Final = [CONF_TIME, CONF_DATE, CONF_DATETIME]

    EXPOSE_TIME_SCHEMA = probatio.Schema(
        {
            probatio.Required(CONF_KNX_EXPOSE_TYPE): probatio.All(
                cv.string, str.lower, probatio.In(EXPOSE_TIME_TYPES)
            ),
            probatio.Required(KNX_ADDRESS): ga_validator,
        }
    )
    EXPOSE_SENSOR_SCHEMA = probatio.Schema(
        {
            probatio.Optional(
                CONF_KNX_EXPOSE_COOLDOWN, default=timedelta(0)
            ): cv.positive_time_period,
            probatio.Optional(CONF_KNX_EXPOSE_SEND_ON_INIT, default=False): cv.boolean,
            probatio.Optional(
                CONF_KNX_EXPOSE_PERIODIC_SEND, default=timedelta(0)
            ): cv.positive_time_period,
            probatio.Optional(CONF_RESPOND_TO_READ, default=True): cv.boolean,
            probatio.Required(CONF_KNX_EXPOSE_TYPE): probatio.Any(
                CONF_KNX_EXPOSE_BINARY, sensor_type_validator
            ),
            probatio.Required(KNX_ADDRESS): ga_validator,
            probatio.Required(CONF_ENTITY_ID): cv.entity_id,
            probatio.Optional(CONF_KNX_EXPOSE_ATTRIBUTE): cv.string,
            probatio.Optional(CONF_KNX_EXPOSE_DEFAULT): cv.match_all,
            probatio.Optional(CONF_VALUE_TEMPLATE): cv.template,
        }
    )
    ENTITY_SCHEMA = probatio.Any(EXPOSE_SENSOR_SCHEMA, EXPOSE_TIME_SCHEMA)


class FanSchema(KNXPlatformSchema):
    """Probatio schema for KNX fans."""

    PLATFORM = Platform.FAN

    CONF_STATE_ADDRESS = CONF_STATE_ADDRESS
    CONF_OSCILLATION_ADDRESS = "oscillation_address"
    CONF_OSCILLATION_STATE_ADDRESS = "oscillation_state_address"
    CONF_SWITCH_ADDRESS = "switch_address"
    CONF_SWITCH_STATE_ADDRESS = "switch_state_address"

    ENTITY_SCHEMA = probatio.All(
        _entity_base_schema(PLATFORM).extend(
            {
                probatio.Optional(KNX_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_SWITCH_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_SWITCH_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_OSCILLATION_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_OSCILLATION_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(FanConf.MAX_STEP): cv.byte,
                probatio.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
            }
        ),
        probatio.Any(
            probatio.Schema(
                {probatio.Required(KNX_ADDRESS): object},
                extra=probatio.ALLOW_EXTRA,
            ),
            probatio.Schema(
                {probatio.Required(CONF_SWITCH_ADDRESS): object},
                extra=probatio.ALLOW_EXTRA,
            ),
            msg=(
                f"At least one of '{KNX_ADDRESS}' or"
                f" '{CONF_SWITCH_ADDRESS}' is required."
            ),
        ),
    )


class LightSchema(KNXPlatformSchema):
    """Probatio schema for KNX lights."""

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
        probatio.Optional(CONF_HUE_ADDRESS): ga_list_validator,
        probatio.Optional(CONF_HUE_STATE_ADDRESS): ga_list_validator,
        probatio.Optional(CONF_SATURATION_ADDRESS): ga_list_validator,
        probatio.Optional(CONF_SATURATION_STATE_ADDRESS): ga_list_validator,
    }

    INDIVIDUAL_COLOR_SCHEMA = probatio.Schema(
        {
            probatio.Optional(KNX_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_STATE_ADDRESS): ga_list_validator,
            probatio.Required(CONF_BRIGHTNESS_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_BRIGHTNESS_STATE_ADDRESS): ga_list_validator,
        }
    )

    ENTITY_SCHEMA = probatio.All(
        _entity_base_schema(PLATFORM).extend(
            {
                probatio.Optional(KNX_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_BRIGHTNESS_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_BRIGHTNESS_STATE_ADDRESS): ga_list_validator,
                probatio.Exclusive(CONF_INDIVIDUAL_COLORS, "color"): {
                    probatio.Inclusive(
                        CONF_RED,
                        "individual_colors",
                        msg=(
                            "'red', 'green' and 'blue' are required for individual"
                            " colors configuration"
                        ),
                    ): INDIVIDUAL_COLOR_SCHEMA,
                    probatio.Inclusive(
                        CONF_GREEN,
                        "individual_colors",
                        msg=(
                            "'red', 'green' and 'blue' are required for individual"
                            " colors configuration"
                        ),
                    ): INDIVIDUAL_COLOR_SCHEMA,
                    probatio.Inclusive(
                        CONF_BLUE,
                        "individual_colors",
                        msg=(
                            "'red', 'green' and 'blue' are required for individual"
                            " colors configuration"
                        ),
                    ): INDIVIDUAL_COLOR_SCHEMA,
                    probatio.Optional(CONF_WHITE): INDIVIDUAL_COLOR_SCHEMA,
                },
                probatio.Exclusive(CONF_COLOR_ADDRESS, "color"): ga_list_validator,
                probatio.Optional(CONF_COLOR_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_COLOR_TEMP_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_COLOR_TEMP_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(
                    CONF_COLOR_TEMP_MODE, default=DEFAULT_COLOR_TEMP_MODE
                ): probatio.All(probatio.Upper, cv.enum(ColorTempModes)),
                **HS_COLOR_SCHEMA,
                probatio.Exclusive(CONF_RGBW_ADDRESS, "color"): ga_list_validator,
                probatio.Optional(CONF_RGBW_STATE_ADDRESS): ga_list_validator,
                probatio.Exclusive(CONF_XYY_ADDRESS, "color"): ga_list_validator,
                probatio.Optional(CONF_XYY_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(
                    CONF_MIN_KELVIN, default=DEFAULT_MIN_KELVIN
                ): probatio.All(probatio.Coerce(int), probatio.Range(min=1)),
                probatio.Optional(
                    CONF_MAX_KELVIN, default=DEFAULT_MAX_KELVIN
                ): probatio.All(probatio.Coerce(int), probatio.Range(min=1)),
                probatio.Optional(
                    CONF_SYNC_STATE, default=True
                ): sync_state_no_false_validator,
            }
        ),
        probatio.Any(
            probatio.Schema(
                {probatio.Required(KNX_ADDRESS): object},
                extra=probatio.ALLOW_EXTRA,
            ),
            probatio.Schema(  # brightness addresses are required in INDIVIDUAL_COLOR_SCHEMA
                {probatio.Required(CONF_INDIVIDUAL_COLORS): object},
                extra=probatio.ALLOW_EXTRA,
            ),
            msg="either 'address' or 'individual_colors' is required",
        ),
        probatio.Any(
            probatio.Schema(  # 'brightness' is non-optional for hs-color
                {
                    probatio.Inclusive(
                        CONF_BRIGHTNESS_ADDRESS, "hs_color", msg=_hs_color_inclusion_msg
                    ): object,
                    probatio.Inclusive(
                        CONF_HUE_ADDRESS, "hs_color", msg=_hs_color_inclusion_msg
                    ): object,
                    probatio.Inclusive(
                        CONF_SATURATION_ADDRESS, "hs_color", msg=_hs_color_inclusion_msg
                    ): object,
                },
                extra=probatio.ALLOW_EXTRA,
            ),
            probatio.Schema(  # hs-colors not used
                {
                    probatio.Optional(CONF_HUE_ADDRESS): None,
                    probatio.Optional(CONF_SATURATION_ADDRESS): None,
                },
                extra=probatio.ALLOW_EXTRA,
            ),
            msg=_hs_color_inclusion_msg,
        ),
    )


class NotifySchema(KNXPlatformSchema):
    """Probatio schema for KNX notifications."""

    PLATFORM = Platform.NOTIFY

    ENTITY_SCHEMA = _entity_base_schema(PLATFORM).extend(
        {
            probatio.Optional(CONF_TYPE, default="latin_1"): string_type_validator,
            probatio.Required(KNX_ADDRESS): ga_validator,
        }
    )


class NumberSchema(KNXPlatformSchema):
    """Probatio schema for KNX numbers."""

    PLATFORM = Platform.NUMBER

    ENTITY_SCHEMA = probatio.All(
        _entity_base_schema(PLATFORM).extend(
            {
                probatio.Optional(CONF_RESPOND_TO_READ, default=False): cv.boolean,
                probatio.Optional(CONF_MODE, default=NumberMode.AUTO): probatio.Coerce(
                    NumberMode
                ),
                probatio.Required(CONF_TYPE): numeric_type_validator,
                probatio.Required(KNX_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(NumberConf.MAX): probatio.Coerce(float),
                probatio.Optional(NumberConf.MIN): probatio.Coerce(float),
                probatio.Optional(NumberConf.STEP): cv.positive_float,
                probatio.Optional(CONF_DEVICE_CLASS): NUMBER_DEVICE_CLASSES_SCHEMA,
                probatio.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
                probatio.Optional(
                    CONF_SYNC_STATE, default=True
                ): sync_state_no_false_validator,
            }
        ),
        _number_limit_sub_validator,
    )


class SceneSchema(KNXPlatformSchema):
    """Probatio schema for KNX scenes."""

    PLATFORM = Platform.SCENE

    CONF_SCENE_NUMBER = "scene_number"

    ENTITY_SCHEMA = _entity_base_schema(PLATFORM).extend(
        {
            probatio.Required(KNX_ADDRESS): ga_list_validator,
            probatio.Required(SceneConf.SCENE_NUMBER): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=64)
            ),
        }
    )


class SelectSchema(KNXPlatformSchema):
    """Probatio schema for KNX selects."""

    PLATFORM = Platform.SELECT

    ENTITY_SCHEMA = probatio.All(
        _entity_base_schema(PLATFORM).extend(
            {
                probatio.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
                probatio.Optional(CONF_RESPOND_TO_READ, default=False): cv.boolean,
                probatio.Required(CONF_PAYLOAD_LENGTH): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=0, max=14)
                ),
                probatio.Required(SelectConf.OPTIONS): [
                    {
                        probatio.Required(SelectConf.OPTION): probatio.Coerce(str),
                        probatio.Required(CONF_PAYLOAD): cv.positive_int,
                    }
                ],
                probatio.Required(KNX_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_STATE_ADDRESS): ga_list_validator,
            }
        ),
        select_options_sub_validator,
    )


class SensorSchema(KNXPlatformSchema):
    """Probatio schema for KNX sensors."""

    PLATFORM = Platform.SENSOR

    CONF_ALWAYS_CALLBACK = "always_callback"
    CONF_STATE_ADDRESS = CONF_STATE_ADDRESS
    CONF_SYNC_STATE = CONF_SYNC_STATE

    ENTITY_SCHEMA = probatio.All(
        _entity_base_schema(PLATFORM).extend(
            {
                probatio.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
                probatio.Optional(CONF_ALWAYS_CALLBACK, default=False): cv.boolean,
                probatio.Optional(CONF_SENSOR_STATE_CLASS): STATE_CLASSES_SCHEMA,
                probatio.Required(CONF_TYPE): sensor_type_validator,
                probatio.Required(CONF_STATE_ADDRESS): ga_list_validator,
                probatio.Optional(CONF_DEVICE_CLASS): SENSOR_DEVICE_CLASSES_SCHEMA,
                probatio.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
            }
        ),
        _sensor_attribute_sub_validator,
    )


class SwitchSchema(KNXPlatformSchema):
    """Probatio schema for KNX switches."""

    PLATFORM = Platform.SWITCH

    CONF_INVERT = CONF_INVERT
    CONF_STATE_ADDRESS = CONF_STATE_ADDRESS

    ENTITY_SCHEMA = _entity_base_schema(PLATFORM).extend(
        {
            probatio.Optional(CONF_INVERT, default=False): cv.boolean,
            probatio.Optional(CONF_RESPOND_TO_READ, default=False): cv.boolean,
            probatio.Required(KNX_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_STATE_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_DEVICE_CLASS): SWITCH_DEVICE_CLASSES_SCHEMA,
            probatio.Optional(
                CONF_SYNC_STATE, default=True
            ): sync_state_no_false_validator,
        }
    )


class TextSchema(KNXPlatformSchema):
    """Probatio schema for KNX text."""

    PLATFORM = Platform.TEXT

    ENTITY_SCHEMA = _entity_base_schema(PLATFORM).extend(
        {
            probatio.Optional(CONF_RESPOND_TO_READ, default=False): cv.boolean,
            probatio.Optional(CONF_TYPE, default="latin_1"): string_type_validator,
            probatio.Optional(CONF_MODE, default=TextMode.TEXT): probatio.Coerce(
                TextMode
            ),
            probatio.Required(KNX_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_STATE_ADDRESS): ga_list_validator,
            probatio.Optional(
                CONF_SYNC_STATE, default=True
            ): sync_state_no_false_validator,
        }
    )


class TimeSchema(KNXPlatformSchema):
    """Probatio schema for KNX time."""

    PLATFORM = Platform.TIME

    ENTITY_SCHEMA = _entity_base_schema(PLATFORM).extend(
        {
            probatio.Optional(CONF_RESPOND_TO_READ, default=False): cv.boolean,
            probatio.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
            probatio.Required(KNX_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_STATE_ADDRESS): ga_list_validator,
        }
    )


class WeatherSchema(KNXPlatformSchema):
    """Probatio schema for KNX weather station."""

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

    ENTITY_SCHEMA = _entity_base_schema(PLATFORM).extend(
        {
            probatio.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
            probatio.Required(CONF_KNX_TEMPERATURE_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_KNX_BRIGHTNESS_SOUTH_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_KNX_BRIGHTNESS_EAST_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_KNX_BRIGHTNESS_WEST_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_KNX_BRIGHTNESS_NORTH_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_KNX_WIND_SPEED_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_KNX_WIND_BEARING_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_KNX_RAIN_ALARM_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_KNX_FROST_ALARM_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_KNX_WIND_ALARM_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_KNX_DAY_NIGHT_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_KNX_AIR_PRESSURE_ADDRESS): ga_list_validator,
            probatio.Optional(CONF_KNX_HUMIDITY_ADDRESS): ga_list_validator,
        }
    )
