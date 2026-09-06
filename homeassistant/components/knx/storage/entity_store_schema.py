"""KNX entity store schema."""

from collections.abc import Hashable
from enum import StrEnum, unique

import probatio
from xknx.dpt import DPTBase, DPTBinary, DPTNumeric
from xknx.exceptions import ConversionError

from homeassistant.components.climate import HVACMode
from homeassistant.components.number import (
    DEVICE_CLASS_UNITS as NUMBER_DEVICE_CLASS_UNITS,
    NumberMode,
)
from homeassistant.components.sensor import (
    CONF_STATE_CLASS as CONF_SENSOR_STATE_CLASS,
    DEVICE_CLASS_UNITS as SENSOR_DEVICE_CLASS_UNITS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.text import TextMode
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_ENTITY_ID,
    CONF_MODE,
    CONF_NAME,
    CONF_PAYLOAD,
    CONF_PLATFORM,
    CONF_UNIT_OF_MEASUREMENT,
    Platform,
)
from homeassistant.helpers import selector
from homeassistant.helpers.entity import ENTITY_CATEGORIES_SCHEMA
from homeassistant.helpers.typing import VolDictType

from ..const import (
    CONF_CONTEXT_TIMEOUT,
    CONF_IGNORE_INTERNAL_STATE,
    CONF_INVERT,
    CONF_PAYLOAD_LENGTH,
    CONF_RESET_AFTER,
    CONF_RESPOND_TO_READ,
    CONF_SYNC_STATE,
    CONF_VALUE,
    DOMAIN,
    SUPPORTED_PLATFORMS_UI,
    ClimateConf,
    ColorTempModes,
    CoverConf,
    FanConf,
    FanZeroMode,
    NumberConf,
    SceneConf,
    SelectConf,
)
from ..dpt import get_supported_dpts, raw_payload_length
from ..validation import validate_number_attributes, validate_sensor_attributes
from .const import (
    CONF_ALWAYS_CALLBACK,
    CONF_COLOR,
    CONF_COLOR_TEMP_MAX,
    CONF_COLOR_TEMP_MIN,
    CONF_DATA,
    CONF_DEVICE_INFO,
    CONF_DPT,
    CONF_ENTITY,
    CONF_GA_ACTIVE,
    CONF_GA_AIR_PRESSURE,
    CONF_GA_ANGLE,
    CONF_GA_BLUE_BRIGHTNESS,
    CONF_GA_BLUE_SWITCH,
    CONF_GA_BRIGHTNESS,
    CONF_GA_BRIGHTNESS_EAST,
    CONF_GA_BRIGHTNESS_NORTH,
    CONF_GA_BRIGHTNESS_SOUTH,
    CONF_GA_BRIGHTNESS_WEST,
    CONF_GA_COLOR,
    CONF_GA_COLOR_TEMP,
    CONF_GA_CONTROLLER_MODE,
    CONF_GA_CONTROLLER_STATUS,
    CONF_GA_DATE,
    CONF_GA_DATETIME,
    CONF_GA_DAY_NIGHT,
    CONF_GA_FAN_SPEED,
    CONF_GA_FAN_SWING,
    CONF_GA_FAN_SWING_HORIZONTAL,
    CONF_GA_FROST_ALARM,
    CONF_GA_GREEN_BRIGHTNESS,
    CONF_GA_GREEN_SWITCH,
    CONF_GA_HEAT_COOL,
    CONF_GA_HUE,
    CONF_GA_HUMIDITY,
    CONF_GA_HUMIDITY_CURRENT,
    CONF_GA_ON_OFF,
    CONF_GA_OP_MODE_COMFORT,
    CONF_GA_OP_MODE_ECO,
    CONF_GA_OP_MODE_PROTECTION,
    CONF_GA_OP_MODE_STANDBY,
    CONF_GA_OPERATION_MODE,
    CONF_GA_OSCILLATION,
    CONF_GA_POSITION_SET,
    CONF_GA_POSITION_STATE,
    CONF_GA_RAIN_ALARM,
    CONF_GA_RED_BRIGHTNESS,
    CONF_GA_RED_SWITCH,
    CONF_GA_SATURATION,
    CONF_GA_SCENE,
    CONF_GA_SEND,
    CONF_GA_SENSOR,
    CONF_GA_SETPOINT_SHIFT,
    CONF_GA_SPEED,
    CONF_GA_STEP,
    CONF_GA_STOP,
    CONF_GA_SWITCH,
    CONF_GA_TEMPERATURE,
    CONF_GA_TEMPERATURE_CURRENT,
    CONF_GA_TEMPERATURE_TARGET,
    CONF_GA_TEXT,
    CONF_GA_TIME,
    CONF_GA_UP_DOWN,
    CONF_GA_VALVE,
    CONF_GA_WHITE_BRIGHTNESS,
    CONF_GA_WHITE_SWITCH,
    CONF_GA_WIND_ALARM,
    CONF_GA_WIND_BEARING,
    CONF_GA_WIND_SPEED,
    CONF_IGNORE_AUTO_MODE,
    CONF_INVERT_DAY_NIGHT,
    CONF_SPEED,
    CONF_TARGET_TEMPERATURE,
)
from .knx_selector import (
    AllSerializeFirst,
    GASelector,
    GroupSelect,
    GroupSelectOption,
    KnxPayloadSelector,
    KNXSectionFlat,
    KnxSelectOptionsSelector,
    SyncStateSelector,
)

BASE_ENTITY_SCHEMA = probatio.All(
    {
        probatio.Optional(CONF_NAME, default=None): probatio.Maybe(str),
        probatio.Optional(CONF_DEVICE_INFO, default=None): probatio.Maybe(str),
        probatio.Optional(CONF_ENTITY_CATEGORY, default=None): probatio.Any(
            ENTITY_CATEGORIES_SCHEMA, probatio.SetTo(None)
        ),
    },
    probatio.Any(
        probatio.Schema(
            {
                probatio.Required(CONF_NAME): probatio.All(str, probatio.IsTrue()),
            },
            extra=probatio.ALLOW_EXTRA,
        ),
        probatio.Schema(
            {
                probatio.Required(CONF_DEVICE_INFO): str,
            },
            extra=probatio.ALLOW_EXTRA,
        ),
        msg="One of `Device` or `Name` is required",
    ),
)


BINARY_SENSOR_KNX_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_GA_SENSOR): GASelector(
            write=False, state_required=True, valid_dpt="1"
        ),
        probatio.Optional(CONF_INVERT): selector.BooleanSelector(),
        "section_advanced_options": KNXSectionFlat(collapsible=True),
        probatio.Optional(CONF_IGNORE_INTERNAL_STATE): selector.BooleanSelector(),
        probatio.Optional(CONF_CONTEXT_TIMEOUT): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=10, step=0.1, unit_of_measurement="s"
            )
        ),
        probatio.Optional(CONF_RESET_AFTER): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=600, step=0.1, unit_of_measurement="s"
            )
        ),
        probatio.Required(CONF_SYNC_STATE, default=True): SyncStateSelector(
            allow_false=True
        ),
    },
)


def _button_data_sub_validator(config: dict) -> dict:
    """Validate data matching configured DPT."""
    dpt = config[CONF_GA_SEND].get(CONF_DPT)
    transcoder = None
    if dpt:
        transcoder = DPTBase.parse_transcoder(dpt)
        assert transcoder is not None  # already checked by GASelector

        if CONF_VALUE in config[CONF_DATA]:
            try:
                transcoder.to_knx(config[CONF_DATA][CONF_VALUE])
            except ConversionError as ex:
                raise probatio.Invalid(
                    f"Value invalid for DPT {transcoder.dpt_number_str()}",
                    path=([CONF_DATA]),
                ) from ex
        elif CONF_PAYLOAD_LENGTH in config[CONF_DATA]:
            length = config[CONF_DATA][CONF_PAYLOAD_LENGTH]
            if length != transcoder.payload_length or (
                length != 0 and transcoder.payload_type is DPTBinary
            ):
                raise probatio.Invalid(
                    f"Payload length invalid for DPT {transcoder.dpt_number_str()}",
                    path=([CONF_DATA]),
                )
        return config
    # without DPT only raw allowed -> payload + payload_length (checked by KnxPayloadSelector)
    if CONF_PAYLOAD_LENGTH in config[CONF_DATA]:
        return config
    raise probatio.Invalid("Invalid configuration for button entity")


BUTTON_KNX_SCHEMA = AllSerializeFirst(
    probatio.Schema(
        {
            probatio.Required(CONF_GA_SEND): GASelector(
                state=False,
                write_required=True,
                passive=False,
                dpt=["numeric", "enum", "complex", "string"],
                dpt_required=False,  # for raw payload support
            ),
            probatio.Required(CONF_DATA): KnxPayloadSelector(ga_path=CONF_GA_SEND),
        },
    ),
    _button_data_sub_validator,
)

COVER_KNX_SCHEMA = AllSerializeFirst(
    probatio.Schema(
        {
            probatio.Optional(CONF_GA_UP_DOWN): GASelector(state=False, valid_dpt="1"),
            probatio.Optional(CoverConf.INVERT_UPDOWN): selector.BooleanSelector(),
            probatio.Optional(CONF_GA_STOP): GASelector(state=False, valid_dpt="1"),
            probatio.Optional(CONF_GA_STEP): GASelector(state=False, valid_dpt="1"),
            "section_position_control": KNXSectionFlat(collapsible=True),
            probatio.Optional(CONF_GA_POSITION_SET): GASelector(
                state=False, valid_dpt="5.001"
            ),
            probatio.Optional(CONF_GA_POSITION_STATE): GASelector(
                write=False, valid_dpt="5.001"
            ),
            probatio.Optional(CoverConf.INVERT_POSITION): selector.BooleanSelector(),
            "section_tilt_control": KNXSectionFlat(collapsible=True),
            probatio.Optional(CONF_GA_ANGLE): GASelector(valid_dpt="5.001"),
            probatio.Optional(CoverConf.INVERT_ANGLE): selector.BooleanSelector(),
            "section_travel_time": KNXSectionFlat(),
            probatio.Required(
                CoverConf.TRAVELLING_TIME_UP, default=25
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=1000, step=0.1, unit_of_measurement="s"
                )
            ),
            probatio.Required(
                CoverConf.TRAVELLING_TIME_DOWN, default=25
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=1000, step=0.1, unit_of_measurement="s"
                )
            ),
            probatio.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
        },
        extra=probatio.REMOVE_EXTRA,
    ),
    probatio.Any(
        probatio.Schema(
            {
                probatio.Required(CONF_GA_UP_DOWN): GASelector(
                    state=False, write_required=True
                )
            },
            extra=probatio.ALLOW_EXTRA,
        ),
        probatio.Schema(
            {
                probatio.Required(CONF_GA_POSITION_SET): GASelector(
                    state=False, write_required=True
                )
            },
            extra=probatio.ALLOW_EXTRA,
        ),
        msg=(
            "At least one of 'Open/Close control' or"
            " 'Position - Set position' is required."
        ),
    ),
)

DATE_KNX_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_GA_DATE): GASelector(
            write_required=True, valid_dpt="11.001"
        ),
        probatio.Optional(
            CONF_RESPOND_TO_READ, default=False
        ): selector.BooleanSelector(),
        probatio.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
    }
)

DATETIME_KNX_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_GA_DATETIME): GASelector(
            write_required=True, valid_dpt="19.001"
        ),
        probatio.Optional(
            CONF_RESPOND_TO_READ, default=False
        ): selector.BooleanSelector(),
        probatio.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
    }
)

FAN_KNX_SCHEMA = AllSerializeFirst(
    probatio.Schema(
        {
            probatio.Optional(CONF_GA_SWITCH): GASelector(
                write_required=True, valid_dpt="1"
            ),
            probatio.Optional(CONF_SPEED): GroupSelect(
                GroupSelectOption(
                    translation_key="percentage_mode",
                    schema={
                        probatio.Required(CONF_GA_SPEED): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                    },
                ),
                GroupSelectOption(
                    translation_key="step_mode",
                    schema={
                        probatio.Required(CONF_GA_STEP): GASelector(
                            write_required=True, valid_dpt="5.010"
                        ),
                        probatio.Required(
                            FanConf.MAX_STEP, default=3
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1,
                                max=100,
                                step=1,
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                    },
                ),
                collapsible=False,
            ),
            probatio.Optional(CONF_GA_OSCILLATION): GASelector(
                write_required=True, valid_dpt="1"
            ),
            probatio.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
        }
    ),
    probatio.Any(
        probatio.Schema(
            {probatio.Required(CONF_GA_SWITCH): object},
            extra=probatio.ALLOW_EXTRA,
        ),
        probatio.Schema(
            {probatio.Required(CONF_SPEED): object},
            extra=probatio.ALLOW_EXTRA,
        ),
        msg=("At least one of 'Switch' or 'Fan speed' is required."),
    ),
)


@unique
class LightColorMode(StrEnum):
    """Enum for light color mode."""

    RGB = "232.600"
    RGBW = "251.600"
    XYY = "242.600"


_hs_color_inclusion_msg = (
    "'Hue', 'Saturation' and 'Brightness' addresses are required for HSV configuration"
)


LIGHT_KNX_SCHEMA = AllSerializeFirst(
    probatio.Schema(
        {
            probatio.Optional(CONF_GA_SWITCH): GASelector(
                write_required=True, valid_dpt="1"
            ),
            probatio.Optional(CONF_GA_BRIGHTNESS): GASelector(
                write_required=True, valid_dpt="5.001"
            ),
            "section_color_temp": KNXSectionFlat(collapsible=True),
            probatio.Optional(CONF_GA_COLOR_TEMP): GASelector(
                write_required=True, dpt=ColorTempModes
            ),
            probatio.Required(CONF_COLOR_TEMP_MIN, default=2700): AllSerializeFirst(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=10000, step=1, unit_of_measurement="K"
                    )
                ),
                probatio.Coerce(int),
            ),
            probatio.Required(CONF_COLOR_TEMP_MAX, default=6000): AllSerializeFirst(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=10000, step=1, unit_of_measurement="K"
                    )
                ),
                probatio.Coerce(int),
            ),
            probatio.Optional(CONF_COLOR): GroupSelect(
                GroupSelectOption(
                    translation_key="single_address",
                    schema={
                        probatio.Optional(CONF_GA_COLOR): GASelector(
                            write_required=True, dpt=LightColorMode
                        )
                    },
                ),
                GroupSelectOption(
                    translation_key="individual_addresses",
                    schema={
                        probatio.Optional(CONF_GA_RED_SWITCH): GASelector(
                            write_required=False, valid_dpt="1"
                        ),
                        probatio.Required(CONF_GA_RED_BRIGHTNESS): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                        probatio.Optional(CONF_GA_GREEN_SWITCH): GASelector(
                            write_required=False, valid_dpt="1"
                        ),
                        probatio.Required(CONF_GA_GREEN_BRIGHTNESS): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                        probatio.Optional(CONF_GA_BLUE_SWITCH): GASelector(
                            write_required=False, valid_dpt="1"
                        ),
                        probatio.Required(CONF_GA_BLUE_BRIGHTNESS): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                        probatio.Optional(CONF_GA_WHITE_SWITCH): GASelector(
                            write_required=False, valid_dpt="1"
                        ),
                        probatio.Optional(CONF_GA_WHITE_BRIGHTNESS): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                    },
                ),
                GroupSelectOption(
                    translation_key="hsv_addresses",
                    schema={
                        probatio.Required(CONF_GA_HUE): GASelector(
                            write_required=True, valid_dpt="5.003"
                        ),
                        probatio.Required(CONF_GA_SATURATION): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                    },
                ),
            ),
            probatio.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
        }
    ),
    probatio.Any(
        probatio.Schema(
            {probatio.Required(CONF_GA_SWITCH): object},
            extra=probatio.ALLOW_EXTRA,
        ),
        probatio.Schema(  # brightness addresses are required in INDIVIDUAL_COLOR_SCHEMA
            {
                probatio.Required(CONF_COLOR): {
                    probatio.Required(CONF_GA_RED_BRIGHTNESS): object
                }
            },
            extra=probatio.ALLOW_EXTRA,
        ),
        msg="either 'address' or 'individual_colors' is required",
    ),
    probatio.Any(
        probatio.Schema(  # 'brightness' is non-optional for hs-color
            {
                probatio.Required(
                    CONF_GA_BRIGHTNESS, msg=_hs_color_inclusion_msg
                ): object,
                probatio.Required(CONF_COLOR): {
                    probatio.Required(CONF_GA_HUE, msg=_hs_color_inclusion_msg): object,
                    probatio.Required(
                        CONF_GA_SATURATION, msg=_hs_color_inclusion_msg
                    ): object,
                },
            },
            extra=probatio.ALLOW_EXTRA,
        ),
        probatio.Schema(  # hs-colors not used
            {
                probatio.Optional(CONF_COLOR): {
                    probatio.Optional(CONF_GA_HUE): None,
                    probatio.Optional(CONF_GA_SATURATION): None,
                },
            },
            extra=probatio.ALLOW_EXTRA,
        ),
        msg=_hs_color_inclusion_msg,
    ),
)


NOTIFY_KNX_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_GA_SEND): GASelector(
            state=False, passive=False, write_required=True, dpt=["string"]
        ),
    }
)


def _number_limit_sub_validator(config: dict) -> dict:
    """Validate min, max, and step values for a number entity."""
    dpt = config[CONF_GA_SENSOR][CONF_DPT]
    transcoder = DPTNumeric.parse_transcoder(dpt)
    assert transcoder is not None  # already checked by GASelector
    return validate_number_attributes(transcoder, config)


NUMBER_KNX_SCHEMA = AllSerializeFirst(
    probatio.Schema(
        {
            probatio.Required(CONF_GA_SENSOR): GASelector(
                write_required=True, dpt=["numeric"]
            ),
            probatio.Optional(
                CONF_RESPOND_TO_READ, default=False
            ): selector.BooleanSelector(),
            "section_advanced_options": KNXSectionFlat(collapsible=True),
            probatio.Required(
                CONF_MODE, default=NumberMode.AUTO
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(NumberMode),
                    translation_key="component.knx.config_panel.entities.create.number.knx.mode",
                ),
            ),
            probatio.Optional(NumberConf.MIN): selector.NumberSelector(),
            probatio.Optional(NumberConf.MAX): selector.NumberSelector(),
            probatio.Optional(NumberConf.STEP): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, step="any", mode=selector.NumberSelectorMode.BOX
                )
            ),
            probatio.Optional(CONF_UNIT_OF_MEASUREMENT): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=sorted(
                        {
                            str(unit)
                            for units in NUMBER_DEVICE_CLASS_UNITS.values()
                            for unit in units
                            if unit is not None
                        }
                    ),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                ),
            ),
            probatio.Optional(CONF_DEVICE_CLASS): selector.DeviceClassSelector(
                selector.DeviceClassSelectorConfig(domain=Platform.NUMBER)
            ),
            probatio.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
        },
    ),
    _number_limit_sub_validator,
)

SCENE_KNX_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_GA_SCENE): GASelector(
            state=False,
            passive=False,
            write_required=True,
            valid_dpt=["17.001", "18.001"],
        ),
        probatio.Required(SceneConf.SCENE_NUMBER): AllSerializeFirst(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=64, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            probatio.Coerce(int),
        ),
    },
)


def _select_options_sub_validator(config: dict) -> dict:
    """Validate select options against the configured DPT.

    The `options_source` group selects one of two modes, distinguished by the
    group address key:
    - `ga_enum`: options are derived from a required enum DPT.
    - `ga_custom`: options are configured manually, each as a typed value (needs
      a DPT) or a raw payload. Payload ranges are validated per option by the
      options selector.

    All options are sent to the same group address, so they have to share a
    single payload length - taken from the DPT if one is configured.
    """
    source = config[SelectConf.OPTIONS_SOURCE]
    if SelectConf.GA_ENUM in source:
        dpt = source[SelectConf.GA_ENUM].get(CONF_DPT)
        if dpt is None or get_supported_dpts()[dpt]["dpt_class"] != "enum":
            raise probatio.Invalid(
                "An enum data point type is required",
                path=[SelectConf.OPTIONS_SOURCE, SelectConf.GA_ENUM],
            )
        return config

    error_path: list[Hashable] = [SelectConf.OPTIONS_SOURCE, SelectConf.CUSTOM_OPTIONS]
    options = source[SelectConf.CUSTOM_OPTIONS]
    if not options:
        raise probatio.Invalid("At least one option is required", path=error_path)

    dpt = source[SelectConf.GA_CUSTOM].get(CONF_DPT)
    transcoder = DPTBase.parse_transcoder(dpt) if dpt is not None else None
    payload_length = raw_payload_length(transcoder) if transcoder is not None else None

    options_seen: set[str] = set()
    payloads_seen: set[int] = set()
    for option in options:
        name = option[SelectConf.OPTION]
        if name in options_seen:
            raise probatio.Invalid(
                f"Duplicate option not allowed: {name}", path=error_path
            )
        options_seen.add(name)

        if CONF_VALUE in option:
            if transcoder is None:
                raise probatio.Invalid(
                    f"A data point type is required for typed option '{name}'",
                    path=error_path,
                )
            try:
                payload = int.from_bytes(
                    transcoder.validate_payload(transcoder.to_knx(option[CONF_VALUE])),
                    byteorder="big",
                )
            except ConversionError as ex:
                raise probatio.Invalid(
                    f"Value invalid for option '{name}' with DPT "
                    f"{transcoder.dpt_number_str()}",
                    path=error_path,
                ) from ex
        else:
            option_length = option[CONF_PAYLOAD_LENGTH]
            if payload_length is None:
                payload_length = option_length
            elif option_length != payload_length:
                expected = (
                    f"DPT {transcoder.dpt_number_str()}"
                    if transcoder is not None
                    else "the other options"
                )
                raise probatio.Invalid(
                    f"Payload length {option_length} of option '{name}' doesn't "
                    f"match payload length {payload_length} of {expected}",
                    path=error_path,
                )
            payload = int(option[CONF_PAYLOAD], 16)

        if payload in payloads_seen:
            raise probatio.Invalid(
                f"Duplicate payload not allowed for option '{name}'", path=error_path
            )
        payloads_seen.add(payload)
    return config


SELECT_KNX_SCHEMA = AllSerializeFirst(
    probatio.Schema(
        {
            probatio.Required(SelectConf.OPTIONS_SOURCE): GroupSelect(
                GroupSelectOption(
                    translation_key="from_dpt",
                    schema={
                        probatio.Required(SelectConf.GA_ENUM): GASelector(
                            write_required=True, dpt=["enum"]
                        ),
                    },
                ),
                GroupSelectOption(
                    translation_key="custom",
                    schema={
                        probatio.Required(SelectConf.GA_CUSTOM): GASelector(
                            write_required=True,
                            dpt=["numeric", "enum", "complex", "string"],
                            dpt_required=False,
                        ),
                        probatio.Required(
                            SelectConf.CUSTOM_OPTIONS
                        ): KnxSelectOptionsSelector(ga_path=SelectConf.GA_CUSTOM),
                    },
                ),
                collapsible=False,
            ),
            probatio.Optional(
                CONF_RESPOND_TO_READ, default=False
            ): selector.BooleanSelector(),
            probatio.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
        }
    ),
    _select_options_sub_validator,
)

SWITCH_KNX_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_GA_SWITCH): GASelector(
            write_required=True, valid_dpt="1"
        ),
        probatio.Optional(CONF_INVERT, default=False): selector.BooleanSelector(),
        probatio.Optional(
            CONF_RESPOND_TO_READ, default=False
        ): selector.BooleanSelector(),
        probatio.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
    },
)

TEXT_KNX_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_GA_TEXT): GASelector(
            write_required=True, dpt=["string"]
        ),
        probatio.Required(CONF_MODE, default=TextMode.TEXT): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(TextMode),
                translation_key="component.knx.config_panel.entities.create.text.knx.mode",
            ),
        ),
        probatio.Optional(
            CONF_RESPOND_TO_READ, default=False
        ): selector.BooleanSelector(),
        probatio.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
    },
)

TIME_KNX_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_GA_TIME): GASelector(
            write_required=True, valid_dpt="10.001"
        ),
        probatio.Optional(
            CONF_RESPOND_TO_READ, default=False
        ): selector.BooleanSelector(),
        probatio.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
    }
)


@unique
class ConfSetpointShiftMode(StrEnum):
    """Enum for setpoint shift mode."""

    COUNT = "6.010"
    FLOAT = "9.002"


@unique
class ConfClimateFanSpeedMode(StrEnum):
    """Enum for climate fan speed mode."""

    PERCENTAGE = "5.001"
    STEPS = "5.010"


CLIMATE_KNX_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_GA_TEMPERATURE_CURRENT): GASelector(
            write=False, state_required=True, valid_dpt="9.001"
        ),
        probatio.Optional(CONF_GA_HUMIDITY_CURRENT): GASelector(
            write=False, valid_dpt="9.007"
        ),
        probatio.Required(CONF_TARGET_TEMPERATURE): GroupSelect(
            GroupSelectOption(
                translation_key="group_direct_temp",
                schema={
                    probatio.Required(CONF_GA_TEMPERATURE_TARGET): GASelector(
                        write_required=True, valid_dpt="9.001"
                    ),
                    probatio.Required(
                        ClimateConf.MIN_TEMP, default=7
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-20, max=80, step=1, unit_of_measurement="°C"
                        )
                    ),
                    probatio.Required(
                        ClimateConf.MAX_TEMP, default=28
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=100, step=1, unit_of_measurement="°C"
                        )
                    ),
                    probatio.Required(
                        ClimateConf.TEMPERATURE_STEP, default=0.1
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.1, max=2, step=0.1, unit_of_measurement="K"
                        ),
                    ),
                },
            ),
            GroupSelectOption(
                translation_key="group_setpoint_shift",
                schema={
                    probatio.Required(CONF_GA_TEMPERATURE_TARGET): GASelector(
                        write=False, state_required=True, valid_dpt="9.001"
                    ),
                    probatio.Required(CONF_GA_SETPOINT_SHIFT): GASelector(
                        write_required=True,
                        state_required=True,
                        dpt=ConfSetpointShiftMode,
                    ),
                    probatio.Required(
                        ClimateConf.SETPOINT_SHIFT_MIN, default=-6
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-32, max=0, step=1, unit_of_measurement="K"
                        )
                    ),
                    probatio.Required(
                        ClimateConf.SETPOINT_SHIFT_MAX, default=6
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=32, step=1, unit_of_measurement="K"
                        )
                    ),
                    probatio.Required(
                        ClimateConf.TEMPERATURE_STEP, default=0.1
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.1, max=2, step=0.1, unit_of_measurement="K"
                        ),
                    ),
                },
            ),
            collapsible=False,
        ),
        "section_activity": KNXSectionFlat(collapsible=True),
        probatio.Optional(CONF_GA_ACTIVE): GASelector(write=False, valid_dpt="1"),
        probatio.Optional(CONF_GA_VALVE): GASelector(write=False, valid_dpt="5.001"),
        "section_operation_mode": KNXSectionFlat(collapsible=True),
        probatio.Optional(CONF_GA_OPERATION_MODE): GASelector(valid_dpt="20.102"),
        probatio.Optional(CONF_IGNORE_AUTO_MODE): selector.BooleanSelector(),
        "section_operation_mode_individual": KNXSectionFlat(collapsible=True),
        probatio.Optional(CONF_GA_OP_MODE_COMFORT): GASelector(
            state=False, valid_dpt="1"
        ),
        probatio.Optional(CONF_GA_OP_MODE_ECO): GASelector(state=False, valid_dpt="1"),
        probatio.Optional(CONF_GA_OP_MODE_STANDBY): GASelector(
            state=False, valid_dpt="1"
        ),
        probatio.Optional(CONF_GA_OP_MODE_PROTECTION): GASelector(
            state=False, valid_dpt="1"
        ),
        "section_heat_cool": KNXSectionFlat(collapsible=True),
        probatio.Optional(CONF_GA_HEAT_COOL): GASelector(valid_dpt="1.100"),
        "section_on_off": KNXSectionFlat(collapsible=True),
        probatio.Optional(CONF_GA_ON_OFF): GASelector(valid_dpt="1"),
        probatio.Optional(ClimateConf.ON_OFF_INVERT): selector.BooleanSelector(),
        "section_controller_mode": KNXSectionFlat(collapsible=True),
        probatio.Optional(CONF_GA_CONTROLLER_MODE): GASelector(valid_dpt="20.105"),
        probatio.Optional(CONF_GA_CONTROLLER_STATUS): GASelector(write=False),
        probatio.Required(
            ClimateConf.DEFAULT_CONTROLLER_MODE, default=HVACMode.HEAT
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(HVACMode),
                translation_key="component.climate.selector.hvac_mode",
            )
        ),
        "section_fan": KNXSectionFlat(collapsible=True),
        probatio.Optional(CONF_GA_FAN_SPEED): GASelector(dpt=ConfClimateFanSpeedMode),
        probatio.Required(ClimateConf.FAN_MAX_STEP, default=3): AllSerializeFirst(
            selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=100, step=1)
            ),
            probatio.Coerce(int),
        ),
        probatio.Required(
            ClimateConf.FAN_ZERO_MODE, default=FanZeroMode.OFF
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(FanZeroMode),
                translation_key="component.knx.config_panel.entities.create.climate.knx.fan_zero_mode",
            )
        ),
        probatio.Optional(CONF_GA_FAN_SWING): GASelector(valid_dpt="1"),
        probatio.Optional(CONF_GA_FAN_SWING_HORIZONTAL): GASelector(valid_dpt="1"),
        probatio.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
    },
)


def _sensor_attribute_sub_validator(config: dict) -> dict:
    """Validate state_class, device_class and unit compatibility."""
    dpt = config[CONF_GA_SENSOR][CONF_DPT]
    dpt_metadata = get_supported_dpts()[dpt]
    return validate_sensor_attributes(dpt_metadata, config)


SENSOR_KNX_SCHEMA = AllSerializeFirst(
    probatio.Schema(
        {
            probatio.Required(CONF_GA_SENSOR): GASelector(
                write=False, state_required=True, dpt=["numeric", "string"]
            ),
            "section_advanced_options": KNXSectionFlat(collapsible=True),
            probatio.Optional(CONF_UNIT_OF_MEASUREMENT): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=sorted(
                        {
                            str(unit)
                            for units in SENSOR_DEVICE_CLASS_UNITS.values()
                            for unit in units
                            if unit is not None
                        }
                    ),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="component.knx.selector.sensor_unit_of_measurement",
                    custom_value=True,
                ),
            ),
            probatio.Optional(CONF_DEVICE_CLASS): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        cls.value
                        for cls in SensorDeviceClass
                        if cls != SensorDeviceClass.ENUM
                    ],
                    translation_key="component.knx.selector.sensor_device_class",
                    sort=True,
                )
            ),
            probatio.Optional(CONF_SENSOR_STATE_CLASS): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(SensorStateClass),
                    translation_key="component.knx.selector.sensor_state_class",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            probatio.Optional(CONF_ALWAYS_CALLBACK): selector.BooleanSelector(),
            probatio.Required(CONF_SYNC_STATE, default=True): SyncStateSelector(
                allow_false=True
            ),
        },
    ),
    _sensor_attribute_sub_validator,
)

WEATHER_KNX_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_GA_TEMPERATURE): GASelector(
            write=False, state_required=True, valid_dpt="9.001"
        ),
        probatio.Optional(CONF_GA_HUMIDITY): GASelector(write=False, valid_dpt="9.007"),
        probatio.Optional(CONF_GA_AIR_PRESSURE): GASelector(
            write=False, valid_dpt=["9.006", "14.058"]
        ),
        probatio.Optional(CONF_GA_WIND_SPEED): GASelector(
            write=False, valid_dpt="9.005"
        ),
        probatio.Optional(CONF_GA_WIND_BEARING): GASelector(
            write=False, valid_dpt="5.003"
        ),
        "section_brightness": KNXSectionFlat(collapsible=True),
        probatio.Optional(CONF_GA_BRIGHTNESS_EAST): GASelector(
            write=False, valid_dpt="9.004"
        ),
        probatio.Optional(CONF_GA_BRIGHTNESS_SOUTH): GASelector(
            write=False, valid_dpt="9.004"
        ),
        probatio.Optional(CONF_GA_BRIGHTNESS_WEST): GASelector(
            write=False, valid_dpt="9.004"
        ),
        probatio.Optional(CONF_GA_BRIGHTNESS_NORTH): GASelector(
            write=False, valid_dpt="9.004"
        ),
        "section_day_night": KNXSectionFlat(collapsible=True),
        probatio.Optional(CONF_GA_DAY_NIGHT): GASelector(
            write=False, valid_dpt="1.024"
        ),
        probatio.Optional(
            CONF_INVERT_DAY_NIGHT, default=False
        ): selector.BooleanSelector(),
        "section_alarms": KNXSectionFlat(collapsible=True),
        probatio.Optional(CONF_GA_RAIN_ALARM): GASelector(write=False, valid_dpt="1"),
        probatio.Optional(CONF_GA_FROST_ALARM): GASelector(write=False, valid_dpt="1"),
        probatio.Optional(CONF_GA_WIND_ALARM): GASelector(write=False, valid_dpt="1"),
        probatio.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
    }
)

KNX_SCHEMA_FOR_PLATFORM = {
    Platform.BINARY_SENSOR: BINARY_SENSOR_KNX_SCHEMA,
    Platform.BUTTON: BUTTON_KNX_SCHEMA,
    Platform.CLIMATE: CLIMATE_KNX_SCHEMA,
    Platform.COVER: COVER_KNX_SCHEMA,
    Platform.DATE: DATE_KNX_SCHEMA,
    Platform.DATETIME: DATETIME_KNX_SCHEMA,
    Platform.FAN: FAN_KNX_SCHEMA,
    Platform.LIGHT: LIGHT_KNX_SCHEMA,
    Platform.NOTIFY: NOTIFY_KNX_SCHEMA,
    Platform.NUMBER: NUMBER_KNX_SCHEMA,
    Platform.SCENE: SCENE_KNX_SCHEMA,
    Platform.SELECT: SELECT_KNX_SCHEMA,
    Platform.SENSOR: SENSOR_KNX_SCHEMA,
    Platform.SWITCH: SWITCH_KNX_SCHEMA,
    Platform.TEXT: TEXT_KNX_SCHEMA,
    Platform.TIME: TIME_KNX_SCHEMA,
    Platform.WEATHER: WEATHER_KNX_SCHEMA,
}

ENTITY_STORE_DATA_SCHEMA = probatio.All(
    probatio.Schema(
        {
            probatio.Required(CONF_PLATFORM): probatio.All(
                probatio.Coerce(Platform),
                probatio.In(SUPPORTED_PLATFORMS_UI),
            ),
            probatio.Required(CONF_DATA): dict,
        },
        extra=probatio.ALLOW_EXTRA,
    ),
    probatio.TaggedUnion(
        CONF_PLATFORM,
        {
            platform: probatio.Schema(
                {
                    probatio.Required(CONF_DATA): probatio.Schema(
                        {
                            probatio.Required(CONF_ENTITY): BASE_ENTITY_SCHEMA,
                            probatio.Required(DOMAIN): knx_schema,
                        },
                        extra=probatio.PREVENT_EXTRA,  # restrict in data key for yaml edit
                    ),
                },
                extra=probatio.ALLOW_EXTRA,  # eg. "type" from WS-endpoint when validating directly
            )
            for platform, knx_schema in KNX_SCHEMA_FOR_PLATFORM.items()
        },
    ),
)

CREATE_ENTITY_BASE_SCHEMA: VolDictType = {
    probatio.Required(CONF_PLATFORM): str,
    probatio.Required(
        CONF_DATA
    ): dict,  # validated by ENTITY_STORE_DATA_SCHEMA for platform
}

UPDATE_ENTITY_BASE_SCHEMA = {
    probatio.Required(CONF_ENTITY_ID): str,
    **CREATE_ENTITY_BASE_SCHEMA,
}
