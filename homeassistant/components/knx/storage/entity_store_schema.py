"""KNX entity store schema."""

from enum import StrEnum, unique

import probatio as prb
import voluptuous as vol
from xknx.dpt import DPTBase, DPTBinary, DPTNumeric
from xknx.exceptions import ConversionError

from homeassistant.components.climate import HVACMode
from homeassistant.components.number import (
    DEVICE_CLASS_UNITS as NUMBER_DEVICE_CLASS_UNITS,
    NumberDeviceClass,
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
)
from ..dpt import get_supported_dpts
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
    CONF_GA_ANGLE,
    CONF_GA_BLUE_BRIGHTNESS,
    CONF_GA_BLUE_SWITCH,
    CONF_GA_BRIGHTNESS,
    CONF_GA_COLOR,
    CONF_GA_COLOR_TEMP,
    CONF_GA_CONTROLLER_MODE,
    CONF_GA_CONTROLLER_STATUS,
    CONF_GA_DATE,
    CONF_GA_DATETIME,
    CONF_GA_FAN_SPEED,
    CONF_GA_FAN_SWING,
    CONF_GA_FAN_SWING_HORIZONTAL,
    CONF_GA_GREEN_BRIGHTNESS,
    CONF_GA_GREEN_SWITCH,
    CONF_GA_HEAT_COOL,
    CONF_GA_HUE,
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
    CONF_GA_TEMPERATURE_CURRENT,
    CONF_GA_TEMPERATURE_TARGET,
    CONF_GA_TEXT,
    CONF_GA_TIME,
    CONF_GA_UP_DOWN,
    CONF_GA_VALVE,
    CONF_GA_WHITE_BRIGHTNESS,
    CONF_GA_WHITE_SWITCH,
    CONF_IGNORE_AUTO_MODE,
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
    SyncStateSelector,
)
from .vol_compat import VolValidator

BASE_ENTITY_SCHEMA = prb.All(
    {
        prb.Optional(CONF_NAME, default=None): prb.Maybe(str),
        prb.Optional(CONF_DEVICE_INFO, default=None): prb.Maybe(str),
        prb.Optional(CONF_ENTITY_CATEGORY, default=None): prb.Any(
            VolValidator(ENTITY_CATEGORIES_SCHEMA), prb.SetTo(None)
        ),
    },
    prb.Any(
        prb.Schema(
            {
                prb.Required(CONF_NAME): prb.All(str, prb.IsTrue()),
            },
            extra=prb.ALLOW_EXTRA,
        ),
        prb.Schema(
            {
                prb.Required(CONF_DEVICE_INFO): str,
            },
            extra=prb.ALLOW_EXTRA,
        ),
        msg="One of `Device` or `Name` is required",
    ),
)


BINARY_SENSOR_KNX_SCHEMA = prb.Schema(
    {
        prb.Required(CONF_GA_SENSOR): GASelector(
            write=False, state_required=True, valid_dpt="1"
        ),
        prb.Optional(CONF_INVERT): VolValidator(selector.BooleanSelector()),
        "section_advanced_options": KNXSectionFlat(collapsible=True),
        prb.Optional(CONF_IGNORE_INTERNAL_STATE): VolValidator(
            selector.BooleanSelector()
        ),
        prb.Optional(CONF_CONTEXT_TIMEOUT): VolValidator(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=10, step=0.1, unit_of_measurement="s"
                )
            )
        ),
        prb.Optional(CONF_RESET_AFTER): VolValidator(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=600, step=0.1, unit_of_measurement="s"
                )
            )
        ),
        prb.Required(CONF_SYNC_STATE, default=True): SyncStateSelector(
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
                raise prb.Invalid(
                    f"Value invalid for DPT {transcoder.dpt_number_str()}",
                    path=([CONF_DATA]),
                ) from ex
        elif CONF_PAYLOAD_LENGTH in config[CONF_DATA]:
            length = config[CONF_DATA][CONF_PAYLOAD_LENGTH]
            if length != transcoder.payload_length or (
                length != 0 and transcoder.payload_type is DPTBinary
            ):
                raise prb.Invalid(
                    f"Payload length invalid for DPT {transcoder.dpt_number_str()}",
                    path=([CONF_DATA]),
                )
        return config
    # without DPT only raw allowed -> payload + payload_length (checked by KnxPayloadSelector)
    if CONF_PAYLOAD_LENGTH in config[CONF_DATA]:
        return config
    raise prb.Invalid("Invalid configuration for button entity")


BUTTON_KNX_SCHEMA = AllSerializeFirst(
    prb.Schema(
        {
            prb.Required(CONF_GA_SEND): GASelector(
                state=False,
                write_required=True,
                passive=False,
                dpt=["numeric", "enum", "complex", "string"],
                dpt_required=False,  # for raw payload support
            ),
            prb.Required(CONF_DATA): KnxPayloadSelector(ga_path=CONF_GA_SEND),
        },
    ),
    _button_data_sub_validator,
)

COVER_KNX_SCHEMA = AllSerializeFirst(
    prb.Schema(
        {
            prb.Optional(CONF_GA_UP_DOWN): GASelector(state=False, valid_dpt="1"),
            prb.Optional(CoverConf.INVERT_UPDOWN): VolValidator(
                selector.BooleanSelector()
            ),
            prb.Optional(CONF_GA_STOP): GASelector(state=False, valid_dpt="1"),
            prb.Optional(CONF_GA_STEP): GASelector(state=False, valid_dpt="1"),
            "section_position_control": KNXSectionFlat(collapsible=True),
            prb.Optional(CONF_GA_POSITION_SET): GASelector(
                state=False, valid_dpt="5.001"
            ),
            prb.Optional(CONF_GA_POSITION_STATE): GASelector(
                write=False, valid_dpt="5.001"
            ),
            prb.Optional(CoverConf.INVERT_POSITION): VolValidator(
                selector.BooleanSelector()
            ),
            "section_tilt_control": KNXSectionFlat(collapsible=True),
            prb.Optional(CONF_GA_ANGLE): GASelector(valid_dpt="5.001"),
            prb.Optional(CoverConf.INVERT_ANGLE): VolValidator(
                selector.BooleanSelector()
            ),
            "section_travel_time": KNXSectionFlat(),
            prb.Required(CoverConf.TRAVELLING_TIME_UP, default=25): VolValidator(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=1000, step=0.1, unit_of_measurement="s"
                    )
                )
            ),
            prb.Required(CoverConf.TRAVELLING_TIME_DOWN, default=25): VolValidator(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=1000, step=0.1, unit_of_measurement="s"
                    )
                )
            ),
            prb.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
        },
        extra=prb.REMOVE_EXTRA,
    ),
    prb.Any(
        prb.Schema(
            {
                prb.Required(CONF_GA_UP_DOWN): GASelector(
                    state=False, write_required=True
                )
            },
            extra=prb.ALLOW_EXTRA,
        ),
        prb.Schema(
            {
                prb.Required(CONF_GA_POSITION_SET): GASelector(
                    state=False, write_required=True
                )
            },
            extra=prb.ALLOW_EXTRA,
        ),
        msg=(
            "At least one of 'Open/Close control' or"
            " 'Position - Set position' is required."
        ),
    ),
)

DATE_KNX_SCHEMA = prb.Schema(
    {
        prb.Required(CONF_GA_DATE): GASelector(write_required=True, valid_dpt="11.001"),
        prb.Optional(CONF_RESPOND_TO_READ, default=False): VolValidator(
            selector.BooleanSelector()
        ),
        prb.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
    }
)

DATETIME_KNX_SCHEMA = prb.Schema(
    {
        prb.Required(CONF_GA_DATETIME): GASelector(
            write_required=True, valid_dpt="19.001"
        ),
        prb.Optional(CONF_RESPOND_TO_READ, default=False): VolValidator(
            selector.BooleanSelector()
        ),
        prb.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
    }
)

FAN_KNX_SCHEMA = AllSerializeFirst(
    prb.Schema(
        {
            prb.Optional(CONF_GA_SWITCH): GASelector(
                write_required=True, valid_dpt="1"
            ),
            prb.Optional(CONF_SPEED): GroupSelect(
                GroupSelectOption(
                    translation_key="percentage_mode",
                    schema={
                        prb.Required(CONF_GA_SPEED): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                    },
                ),
                GroupSelectOption(
                    translation_key="step_mode",
                    schema={
                        prb.Required(CONF_GA_STEP): GASelector(
                            write_required=True, valid_dpt="5.010"
                        ),
                        prb.Required(FanConf.MAX_STEP, default=3): VolValidator(
                            selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    min=1,
                                    max=100,
                                    step=1,
                                    mode=selector.NumberSelectorMode.BOX,
                                )
                            )
                        ),
                    },
                ),
                collapsible=False,
            ),
            prb.Optional(CONF_GA_OSCILLATION): GASelector(
                write_required=True, valid_dpt="1"
            ),
            prb.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
        }
    ),
    prb.Any(
        prb.Schema(
            {prb.Required(CONF_GA_SWITCH): object},
            extra=prb.ALLOW_EXTRA,
        ),
        prb.Schema(
            {prb.Required(CONF_SPEED): object},
            extra=prb.ALLOW_EXTRA,
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
    prb.Schema(
        {
            prb.Optional(CONF_GA_SWITCH): GASelector(
                write_required=True, valid_dpt="1"
            ),
            prb.Optional(CONF_GA_BRIGHTNESS): GASelector(
                write_required=True, valid_dpt="5.001"
            ),
            "section_color_temp": KNXSectionFlat(collapsible=True),
            prb.Optional(CONF_GA_COLOR_TEMP): GASelector(
                write_required=True, dpt=ColorTempModes
            ),
            prb.Required(CONF_COLOR_TEMP_MIN, default=2700): VolValidator(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=10000, step=1, unit_of_measurement="K"
                    )
                )
            ),
            prb.Required(CONF_COLOR_TEMP_MAX, default=6000): VolValidator(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=10000, step=1, unit_of_measurement="K"
                    )
                )
            ),
            prb.Optional(CONF_COLOR): GroupSelect(
                GroupSelectOption(
                    translation_key="single_address",
                    schema={
                        prb.Optional(CONF_GA_COLOR): GASelector(
                            write_required=True, dpt=LightColorMode
                        )
                    },
                ),
                GroupSelectOption(
                    translation_key="individual_addresses",
                    schema={
                        prb.Optional(CONF_GA_RED_SWITCH): GASelector(
                            write_required=False, valid_dpt="1"
                        ),
                        prb.Required(CONF_GA_RED_BRIGHTNESS): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                        prb.Optional(CONF_GA_GREEN_SWITCH): GASelector(
                            write_required=False, valid_dpt="1"
                        ),
                        prb.Required(CONF_GA_GREEN_BRIGHTNESS): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                        prb.Optional(CONF_GA_BLUE_SWITCH): GASelector(
                            write_required=False, valid_dpt="1"
                        ),
                        prb.Required(CONF_GA_BLUE_BRIGHTNESS): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                        prb.Optional(CONF_GA_WHITE_SWITCH): GASelector(
                            write_required=False, valid_dpt="1"
                        ),
                        prb.Optional(CONF_GA_WHITE_BRIGHTNESS): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                    },
                ),
                GroupSelectOption(
                    translation_key="hsv_addresses",
                    schema={
                        prb.Required(CONF_GA_HUE): GASelector(
                            write_required=True, valid_dpt="5.003"
                        ),
                        prb.Required(CONF_GA_SATURATION): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                    },
                ),
            ),
            prb.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
        }
    ),
    prb.Any(
        prb.Schema(
            {prb.Required(CONF_GA_SWITCH): object},
            extra=prb.ALLOW_EXTRA,
        ),
        prb.Schema(  # brightness addresses are required in INDIVIDUAL_COLOR_SCHEMA
            {prb.Required(CONF_COLOR): {prb.Required(CONF_GA_RED_BRIGHTNESS): object}},
            extra=prb.ALLOW_EXTRA,
        ),
        msg="either 'address' or 'individual_colors' is required",
    ),
    prb.Any(
        prb.Schema(  # 'brightness' is non-optional for hs-color
            {
                prb.Required(CONF_GA_BRIGHTNESS, msg=_hs_color_inclusion_msg): object,
                prb.Required(CONF_COLOR): {
                    prb.Required(CONF_GA_HUE, msg=_hs_color_inclusion_msg): object,
                    prb.Required(
                        CONF_GA_SATURATION, msg=_hs_color_inclusion_msg
                    ): object,
                },
            },
            extra=prb.ALLOW_EXTRA,
        ),
        prb.Schema(  # hs-colors not used
            {
                prb.Optional(CONF_COLOR): {
                    prb.Optional(CONF_GA_HUE): None,
                    prb.Optional(CONF_GA_SATURATION): None,
                },
            },
            extra=prb.ALLOW_EXTRA,
        ),
        msg=_hs_color_inclusion_msg,
    ),
)


def _number_limit_sub_validator(config: dict) -> dict:
    """Validate min, max, and step values for a number entity."""
    dpt = config[CONF_GA_SENSOR][CONF_DPT]
    transcoder = DPTNumeric.parse_transcoder(dpt)
    assert transcoder is not None  # already checked by GASelector
    return validate_number_attributes(transcoder, config)


NUMBER_KNX_SCHEMA = AllSerializeFirst(
    prb.Schema(
        {
            prb.Required(CONF_GA_SENSOR): GASelector(
                write_required=True, dpt=["numeric"]
            ),
            prb.Optional(CONF_RESPOND_TO_READ, default=False): VolValidator(
                selector.BooleanSelector()
            ),
            "section_advanced_options": KNXSectionFlat(collapsible=True),
            prb.Required(CONF_MODE, default=NumberMode.AUTO): VolValidator(
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(NumberMode),
                        translation_key="component.knx.config_panel.entities.create.number.knx.mode",
                    ),
                )
            ),
            prb.Optional(NumberConf.MIN): VolValidator(selector.NumberSelector()),
            prb.Optional(NumberConf.MAX): VolValidator(selector.NumberSelector()),
            prb.Optional(NumberConf.STEP): VolValidator(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, step="any", mode=selector.NumberSelectorMode.BOX
                    )
                )
            ),
            prb.Optional(CONF_UNIT_OF_MEASUREMENT): VolValidator(
                selector.SelectSelector(
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
                )
            ),
            prb.Optional(CONF_DEVICE_CLASS): VolValidator(
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[cls.value for cls in NumberDeviceClass],
                        # should align with sensor
                        translation_key="component.knx.selector.sensor_device_class",
                        sort=True,
                    )
                )
            ),
            prb.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
        },
    ),
    VolValidator(_number_limit_sub_validator),
)

SCENE_KNX_SCHEMA = prb.Schema(
    {
        prb.Required(CONF_GA_SCENE): GASelector(
            state=False,
            passive=False,
            write_required=True,
            valid_dpt=["17.001", "18.001"],
        ),
        prb.Required(SceneConf.SCENE_NUMBER): AllSerializeFirst(
            VolValidator(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=64, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                )
            ),
            prb.Coerce(int),
        ),
    },
)

SWITCH_KNX_SCHEMA = prb.Schema(
    {
        prb.Required(CONF_GA_SWITCH): GASelector(write_required=True, valid_dpt="1"),
        prb.Optional(CONF_INVERT, default=False): VolValidator(
            selector.BooleanSelector()
        ),
        prb.Optional(CONF_RESPOND_TO_READ, default=False): VolValidator(
            selector.BooleanSelector()
        ),
        prb.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
    },
)

TEXT_KNX_SCHEMA = prb.Schema(
    {
        prb.Required(CONF_GA_TEXT): GASelector(write_required=True, dpt=["string"]),
        prb.Required(CONF_MODE, default=TextMode.TEXT): VolValidator(
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(TextMode),
                    translation_key="component.knx.config_panel.entities.create.text.knx.mode",
                ),
            )
        ),
        prb.Optional(CONF_RESPOND_TO_READ, default=False): VolValidator(
            selector.BooleanSelector()
        ),
        prb.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
    },
)

TIME_KNX_SCHEMA = prb.Schema(
    {
        prb.Required(CONF_GA_TIME): GASelector(write_required=True, valid_dpt="10.001"),
        prb.Optional(CONF_RESPOND_TO_READ, default=False): VolValidator(
            selector.BooleanSelector()
        ),
        prb.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
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


CLIMATE_KNX_SCHEMA = prb.Schema(
    {
        prb.Required(CONF_GA_TEMPERATURE_CURRENT): GASelector(
            write=False, state_required=True, valid_dpt="9.001"
        ),
        prb.Optional(CONF_GA_HUMIDITY_CURRENT): GASelector(
            write=False, valid_dpt="9.007"
        ),
        prb.Required(CONF_TARGET_TEMPERATURE): GroupSelect(
            GroupSelectOption(
                translation_key="group_direct_temp",
                schema={
                    prb.Required(CONF_GA_TEMPERATURE_TARGET): GASelector(
                        write_required=True, valid_dpt="9.001"
                    ),
                    prb.Required(ClimateConf.MIN_TEMP, default=7): VolValidator(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=-20, max=80, step=1, unit_of_measurement="°C"
                            )
                        )
                    ),
                    prb.Required(ClimateConf.MAX_TEMP, default=28): VolValidator(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=0, max=100, step=1, unit_of_measurement="°C"
                            )
                        )
                    ),
                    prb.Required(
                        ClimateConf.TEMPERATURE_STEP, default=0.1
                    ): VolValidator(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=0.1, max=2, step=0.1, unit_of_measurement="K"
                            ),
                        )
                    ),
                },
            ),
            GroupSelectOption(
                translation_key="group_setpoint_shift",
                schema={
                    prb.Required(CONF_GA_TEMPERATURE_TARGET): GASelector(
                        write=False, state_required=True, valid_dpt="9.001"
                    ),
                    prb.Required(CONF_GA_SETPOINT_SHIFT): GASelector(
                        write_required=True,
                        state_required=True,
                        dpt=ConfSetpointShiftMode,
                    ),
                    prb.Required(
                        ClimateConf.SETPOINT_SHIFT_MIN, default=-6
                    ): VolValidator(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=-32, max=0, step=1, unit_of_measurement="K"
                            )
                        )
                    ),
                    prb.Required(
                        ClimateConf.SETPOINT_SHIFT_MAX, default=6
                    ): VolValidator(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=0, max=32, step=1, unit_of_measurement="K"
                            )
                        )
                    ),
                    prb.Required(
                        ClimateConf.TEMPERATURE_STEP, default=0.1
                    ): VolValidator(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=0.1, max=2, step=0.1, unit_of_measurement="K"
                            ),
                        )
                    ),
                },
            ),
            collapsible=False,
        ),
        "section_activity": KNXSectionFlat(collapsible=True),
        prb.Optional(CONF_GA_ACTIVE): GASelector(write=False, valid_dpt="1"),
        prb.Optional(CONF_GA_VALVE): GASelector(write=False, valid_dpt="5.001"),
        "section_operation_mode": KNXSectionFlat(collapsible=True),
        prb.Optional(CONF_GA_OPERATION_MODE): GASelector(valid_dpt="20.102"),
        prb.Optional(CONF_IGNORE_AUTO_MODE): VolValidator(selector.BooleanSelector()),
        "section_operation_mode_individual": KNXSectionFlat(collapsible=True),
        prb.Optional(CONF_GA_OP_MODE_COMFORT): GASelector(state=False, valid_dpt="1"),
        prb.Optional(CONF_GA_OP_MODE_ECO): GASelector(state=False, valid_dpt="1"),
        prb.Optional(CONF_GA_OP_MODE_STANDBY): GASelector(state=False, valid_dpt="1"),
        prb.Optional(CONF_GA_OP_MODE_PROTECTION): GASelector(
            state=False, valid_dpt="1"
        ),
        "section_heat_cool": KNXSectionFlat(collapsible=True),
        prb.Optional(CONF_GA_HEAT_COOL): GASelector(valid_dpt="1.100"),
        "section_on_off": KNXSectionFlat(collapsible=True),
        prb.Optional(CONF_GA_ON_OFF): GASelector(valid_dpt="1"),
        prb.Optional(ClimateConf.ON_OFF_INVERT): VolValidator(
            selector.BooleanSelector()
        ),
        "section_controller_mode": KNXSectionFlat(collapsible=True),
        prb.Optional(CONF_GA_CONTROLLER_MODE): GASelector(valid_dpt="20.105"),
        prb.Optional(CONF_GA_CONTROLLER_STATUS): GASelector(write=False),
        prb.Required(
            ClimateConf.DEFAULT_CONTROLLER_MODE, default=HVACMode.HEAT
        ): VolValidator(
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(HVACMode),
                    translation_key="component.climate.selector.hvac_mode",
                )
            )
        ),
        "section_fan": KNXSectionFlat(collapsible=True),
        prb.Optional(CONF_GA_FAN_SPEED): GASelector(dpt=ConfClimateFanSpeedMode),
        prb.Required(ClimateConf.FAN_MAX_STEP, default=3): AllSerializeFirst(
            VolValidator(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=100, step=1)
                )
            ),
            prb.Coerce(int),
        ),
        prb.Required(ClimateConf.FAN_ZERO_MODE, default=FanZeroMode.OFF): VolValidator(
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(FanZeroMode),
                    translation_key="component.knx.config_panel.entities.create.climate.knx.fan_zero_mode",
                )
            )
        ),
        prb.Optional(CONF_GA_FAN_SWING): GASelector(valid_dpt="1"),
        prb.Optional(CONF_GA_FAN_SWING_HORIZONTAL): GASelector(valid_dpt="1"),
        prb.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
    },
)


def _sensor_attribute_sub_validator(config: dict) -> dict:
    """Validate state_class, device_class and unit compatibility."""
    dpt = config[CONF_GA_SENSOR][CONF_DPT]
    dpt_metadata = get_supported_dpts()[dpt]
    return validate_sensor_attributes(dpt_metadata, config)


SENSOR_KNX_SCHEMA = AllSerializeFirst(
    prb.Schema(
        {
            prb.Required(CONF_GA_SENSOR): GASelector(
                write=False, state_required=True, dpt=["numeric", "string"]
            ),
            "section_advanced_options": KNXSectionFlat(collapsible=True),
            prb.Optional(CONF_UNIT_OF_MEASUREMENT): VolValidator(
                selector.SelectSelector(
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
                )
            ),
            prb.Optional(CONF_DEVICE_CLASS): VolValidator(
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            cls.value
                            for cls in SensorDeviceClass
                            if cls != SensorDeviceClass.ENUM
                        ],
                        translation_key="component.knx.selector.sensor_device_class",
                        sort=True,
                    )
                )
            ),
            prb.Optional(CONF_SENSOR_STATE_CLASS): VolValidator(
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(SensorStateClass),
                        translation_key="component.knx.selector.sensor_state_class",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            ),
            prb.Optional(CONF_ALWAYS_CALLBACK): VolValidator(
                selector.BooleanSelector()
            ),
            prb.Required(CONF_SYNC_STATE, default=True): SyncStateSelector(
                allow_false=True
            ),
        },
    ),
    VolValidator(_sensor_attribute_sub_validator),
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
    Platform.NUMBER: NUMBER_KNX_SCHEMA,
    Platform.SCENE: SCENE_KNX_SCHEMA,
    Platform.SENSOR: SENSOR_KNX_SCHEMA,
    Platform.SWITCH: SWITCH_KNX_SCHEMA,
    Platform.TEXT: TEXT_KNX_SCHEMA,
    Platform.TIME: TIME_KNX_SCHEMA,
}

ENTITY_STORE_DATA_SCHEMA: prb.All = prb.All(
    prb.Schema(
        {
            prb.Required(CONF_PLATFORM): prb.All(
                prb.Coerce(Platform),
                prb.In(SUPPORTED_PLATFORMS_UI),
            ),
            prb.Required(CONF_DATA): dict,
        },
        extra=prb.ALLOW_EXTRA,
    ),
    prb.TaggedUnion(
        CONF_PLATFORM,
        {
            platform: prb.Schema(
                {
                    prb.Required(CONF_DATA): {
                        prb.Required(CONF_ENTITY): BASE_ENTITY_SCHEMA,
                        prb.Required(DOMAIN): knx_schema,
                    },
                },
                extra=prb.ALLOW_EXTRA,
            )
            for platform, knx_schema in KNX_SCHEMA_FOR_PLATFORM.items()
        },
    ),
)

CREATE_ENTITY_BASE_SCHEMA: VolDictType = {
    vol.Required(CONF_PLATFORM): str,
    vol.Required(CONF_DATA): dict,  # validated by ENTITY_STORE_DATA_SCHEMA for platform
}

UPDATE_ENTITY_BASE_SCHEMA = {
    vol.Required(CONF_ENTITY_ID): str,
    **CREATE_ENTITY_BASE_SCHEMA,
}
