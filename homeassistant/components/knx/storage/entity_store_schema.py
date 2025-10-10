"""KNX entity store schema."""

from enum import StrEnum, unique

import voluptuous as vol

from homeassistant.components.climate import HVACMode
from homeassistant.const import (
    CONF_ENTITY_CATEGORY,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_PLATFORM,
    Platform,
)
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.entity import ENTITY_CATEGORIES_SCHEMA
from homeassistant.helpers.typing import VolDictType, VolSchemaType

from ..const import (
    CONF_CONTEXT_TIMEOUT,
    CONF_IGNORE_INTERNAL_STATE,
    CONF_INVERT,
    CONF_RESET_AFTER,
    CONF_RESPOND_TO_READ,
    CONF_SYNC_STATE,
    DOMAIN,
    SUPPORTED_PLATFORMS_UI,
    ClimateConf,
    ColorTempModes,
    CoverConf,
    FanZeroMode,
)
from .const import (
    CONF_COLOR,
    CONF_COLOR_TEMP_MAX,
    CONF_COLOR_TEMP_MIN,
    CONF_DATA,
    CONF_DEVICE_INFO,
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
    CONF_GA_POSITION_SET,
    CONF_GA_POSITION_STATE,
    CONF_GA_RED_BRIGHTNESS,
    CONF_GA_RED_SWITCH,
    CONF_GA_SATURATION,
    CONF_GA_SENSOR,
    CONF_GA_SETPOINT_SHIFT,
    CONF_GA_STEP,
    CONF_GA_STOP,
    CONF_GA_SWITCH,
    CONF_GA_TEMPERATURE_CURRENT,
    CONF_GA_TEMPERATURE_TARGET,
    CONF_GA_UP_DOWN,
    CONF_GA_VALVE,
    CONF_GA_WHITE_BRIGHTNESS,
    CONF_GA_WHITE_SWITCH,
    CONF_IGNORE_AUTO_MODE,
    CONF_TARGET_TEMPERATURE,
)
from .knx_selector import (
    AllSerializeFirst,
    GASelector,
    GroupSelect,
    GroupSelectOption,
    KNXSectionFlat,
    SyncStateSelector,
)

BASE_ENTITY_SCHEMA = vol.All(
    {
        vol.Optional(CONF_NAME, default=None): vol.Maybe(str),
        vol.Optional(CONF_DEVICE_INFO, default=None): vol.Maybe(str),
        vol.Optional(CONF_ENTITY_CATEGORY, default=None): vol.Any(
            ENTITY_CATEGORIES_SCHEMA, vol.SetTo(None)
        ),
    },
    vol.Any(
        vol.Schema(
            {
                vol.Required(CONF_NAME): vol.All(str, vol.IsTrue()),
            },
            extra=vol.ALLOW_EXTRA,
        ),
        vol.Schema(
            {
                vol.Required(CONF_DEVICE_INFO): str,
            },
            extra=vol.ALLOW_EXTRA,
        ),
        msg="One of `Device` or `Name` is required",
    ),
)


BINARY_SENSOR_KNX_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_GA_SENSOR): GASelector(
            write=False, state_required=True, valid_dpt="1"
        ),
        vol.Optional(CONF_INVERT): selector.BooleanSelector(),
        "section_advanced_options": KNXSectionFlat(collapsible=True),
        vol.Optional(CONF_IGNORE_INTERNAL_STATE): selector.BooleanSelector(),
        vol.Optional(CONF_CONTEXT_TIMEOUT): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=10, step=0.1, unit_of_measurement="s"
            )
        ),
        vol.Optional(CONF_RESET_AFTER): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=600, step=0.1, unit_of_measurement="s"
            )
        ),
        vol.Required(CONF_SYNC_STATE, default=True): SyncStateSelector(),
    },
)

COVER_KNX_SCHEMA = AllSerializeFirst(
    vol.Schema(
        {
            vol.Optional(CONF_GA_UP_DOWN): GASelector(state=False, valid_dpt="1"),
            vol.Optional(CoverConf.INVERT_UPDOWN): selector.BooleanSelector(),
            vol.Optional(CONF_GA_STOP): GASelector(state=False, valid_dpt="1"),
            vol.Optional(CONF_GA_STEP): GASelector(state=False, valid_dpt="1"),
            "section_position_control": KNXSectionFlat(collapsible=True),
            vol.Optional(CONF_GA_POSITION_SET): GASelector(
                state=False, valid_dpt="5.001"
            ),
            vol.Optional(CONF_GA_POSITION_STATE): GASelector(
                write=False, valid_dpt="5.001"
            ),
            vol.Optional(CoverConf.INVERT_POSITION): selector.BooleanSelector(),
            "section_tilt_control": KNXSectionFlat(collapsible=True),
            vol.Optional(CONF_GA_ANGLE): GASelector(valid_dpt="5.001"),
            vol.Optional(CoverConf.INVERT_ANGLE): selector.BooleanSelector(),
            "section_travel_time": KNXSectionFlat(),
            vol.Required(
                CoverConf.TRAVELLING_TIME_UP, default=25
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=1000, step=0.1, unit_of_measurement="s"
                )
            ),
            vol.Required(
                CoverConf.TRAVELLING_TIME_DOWN, default=25
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=1000, step=0.1, unit_of_measurement="s"
                )
            ),
            vol.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
        },
        extra=vol.REMOVE_EXTRA,
    ),
    vol.Any(
        vol.Schema(
            {
                vol.Required(CONF_GA_UP_DOWN): GASelector(
                    state=False, write_required=True
                )
            },
            extra=vol.ALLOW_EXTRA,
        ),
        vol.Schema(
            {
                vol.Required(CONF_GA_POSITION_SET): GASelector(
                    state=False, write_required=True
                )
            },
            extra=vol.ALLOW_EXTRA,
        ),
        msg=(
            "At least one of 'Open/Close control' or"
            " 'Position - Set position' is required."
        ),
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
    vol.Schema(
        {
            vol.Optional(CONF_GA_SWITCH): GASelector(
                write_required=True, valid_dpt="1"
            ),
            vol.Optional(CONF_GA_BRIGHTNESS): GASelector(
                write_required=True, valid_dpt="5.001"
            ),
            "section_color_temp": KNXSectionFlat(collapsible=True),
            vol.Optional(CONF_GA_COLOR_TEMP): GASelector(
                write_required=True, dpt=ColorTempModes
            ),
            vol.Required(CONF_COLOR_TEMP_MIN, default=2700): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=10000, step=1, unit_of_measurement="K"
                )
            ),
            vol.Required(CONF_COLOR_TEMP_MAX, default=6000): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=10000, step=1, unit_of_measurement="K"
                )
            ),
            vol.Optional(CONF_COLOR): GroupSelect(
                GroupSelectOption(
                    translation_key="single_address",
                    schema={
                        vol.Optional(CONF_GA_COLOR): GASelector(
                            write_required=True, dpt=LightColorMode
                        )
                    },
                ),
                GroupSelectOption(
                    translation_key="individual_addresses",
                    schema={
                        vol.Optional(CONF_GA_RED_SWITCH): GASelector(
                            write_required=False, valid_dpt="1"
                        ),
                        vol.Required(CONF_GA_RED_BRIGHTNESS): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                        vol.Optional(CONF_GA_GREEN_SWITCH): GASelector(
                            write_required=False, valid_dpt="1"
                        ),
                        vol.Required(CONF_GA_GREEN_BRIGHTNESS): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                        vol.Optional(CONF_GA_BLUE_SWITCH): GASelector(
                            write_required=False, valid_dpt="1"
                        ),
                        vol.Required(CONF_GA_BLUE_BRIGHTNESS): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                        vol.Optional(CONF_GA_WHITE_SWITCH): GASelector(
                            write_required=False, valid_dpt="1"
                        ),
                        vol.Optional(CONF_GA_WHITE_BRIGHTNESS): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                    },
                ),
                GroupSelectOption(
                    translation_key="hsv_addresses",
                    schema={
                        vol.Required(CONF_GA_HUE): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                        vol.Required(CONF_GA_SATURATION): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                    },
                ),
            ),
            vol.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
        }
    ),
    vol.Any(
        vol.Schema(
            {vol.Required(CONF_GA_SWITCH): object},
            extra=vol.ALLOW_EXTRA,
        ),
        vol.Schema(  # brightness addresses are required in INDIVIDUAL_COLOR_SCHEMA
            {vol.Required(CONF_COLOR): {vol.Required(CONF_GA_RED_BRIGHTNESS): object}},
            extra=vol.ALLOW_EXTRA,
        ),
        msg="either 'address' or 'individual_colors' is required",
    ),
    vol.Any(
        vol.Schema(  # 'brightness' is non-optional for hs-color
            {
                vol.Required(CONF_GA_BRIGHTNESS, msg=_hs_color_inclusion_msg): object,
                vol.Required(CONF_COLOR): {
                    vol.Required(CONF_GA_HUE, msg=_hs_color_inclusion_msg): object,
                    vol.Required(
                        CONF_GA_SATURATION, msg=_hs_color_inclusion_msg
                    ): object,
                },
            },
            extra=vol.ALLOW_EXTRA,
        ),
        vol.Schema(  # hs-colors not used
            {
                vol.Optional(CONF_COLOR): {
                    vol.Optional(CONF_GA_HUE): None,
                    vol.Optional(CONF_GA_SATURATION): None,
                },
            },
            extra=vol.ALLOW_EXTRA,
        ),
        msg=_hs_color_inclusion_msg,
    ),
)

SWITCH_KNX_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_GA_SWITCH): GASelector(write_required=True, valid_dpt="1"),
        vol.Optional(CONF_INVERT, default=False): selector.BooleanSelector(),
        vol.Optional(CONF_RESPOND_TO_READ, default=False): selector.BooleanSelector(),
        vol.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
    },
)


@unique
class ConfSetpointShiftMode(StrEnum):
    """Enum for setpoint shift mode."""

    COUNT = "6.010"
    FLOAT = "9.002"


@unique
class ActiveMode(StrEnum):
    """Enum for active mode."""

    BINARY = "1"
    VALVE = "5.001"


@unique
class ClimateFanSpeedMode(StrEnum):
    """Enum for climate fan speed mode."""

    PERCENTAGE = "5.001"
    STEPS = "5.010"


CLIMATE_KNX_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_GA_TEMPERATURE_CURRENT): GASelector(
            write=False, state_required=True, valid_dpt="9.001"
        ),
        vol.Optional(CONF_GA_HUMIDITY_CURRENT): GASelector(
            write=False, valid_dpt="9.002"
        ),
        vol.Required(CONF_TARGET_TEMPERATURE): GroupSelect(
            GroupSelectOption(
                translation_key="group_direct_temp",
                schema={
                    vol.Required(CONF_GA_TEMPERATURE_TARGET): GASelector(
                        write_required=True, valid_dpt="9.001"
                    ),
                    vol.Required(
                        ClimateConf.MIN_TEMP, default=7
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-20, max=80, step=1, unit_of_measurement="°C"
                        )
                    ),
                    vol.Required(
                        ClimateConf.MAX_TEMP, default=28
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=100, step=1, unit_of_measurement="°C"
                        )
                    ),
                    vol.Required(
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
                    vol.Required(CONF_GA_TEMPERATURE_TARGET): GASelector(
                        write=False, state_required=True, valid_dpt="9.001"
                    ),
                    vol.Required(CONF_GA_SETPOINT_SHIFT): GASelector(
                        write_required=True,
                        state_required=True,
                        dpt=ConfSetpointShiftMode,
                    ),
                    vol.Required(
                        ClimateConf.SETPOINT_SHIFT_MIN, default=-6
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-32, max=0, step=1, unit_of_measurement="K"
                        )
                    ),
                    vol.Required(
                        ClimateConf.SETPOINT_SHIFT_MAX, default=6
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=32, step=1, unit_of_measurement="K"
                        )
                    ),
                    vol.Required(
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
        vol.Optional(CONF_GA_ACTIVE): GASelector(write=False, valid_dpt="1"),
        vol.Optional(CONF_GA_VALVE): GASelector(write=False, valid_dpt="5.001"),
        "section_operation_mode": KNXSectionFlat(collapsible=True),
        vol.Optional(CONF_GA_OPERATION_MODE): GASelector(valid_dpt="20.102"),
        vol.Optional(CONF_IGNORE_AUTO_MODE): selector.BooleanSelector(),
        "section_operation_mode_individual": KNXSectionFlat(collapsible=True),
        vol.Optional(CONF_GA_OP_MODE_COMFORT): GASelector(state=False, valid_dpt="1"),
        vol.Optional(CONF_GA_OP_MODE_ECO): GASelector(state=False, valid_dpt="1"),
        vol.Optional(CONF_GA_OP_MODE_STANDBY): GASelector(state=False, valid_dpt="1"),
        vol.Optional(CONF_GA_OP_MODE_PROTECTION): GASelector(
            state=False, valid_dpt="1"
        ),
        "section_heat_cool": KNXSectionFlat(collapsible=True),
        vol.Optional(CONF_GA_HEAT_COOL): GASelector(valid_dpt="1.100"),
        "section_on_off": KNXSectionFlat(collapsible=True),
        vol.Optional(CONF_GA_ON_OFF): GASelector(valid_dpt="1"),
        vol.Optional(ClimateConf.ON_OFF_INVERT): selector.BooleanSelector(),
        "section_controller_mode": KNXSectionFlat(collapsible=True),
        vol.Optional(CONF_GA_CONTROLLER_MODE): GASelector(valid_dpt="20.105"),
        vol.Optional(CONF_GA_CONTROLLER_STATUS): GASelector(write=False),
        vol.Required(
            ClimateConf.DEFAULT_CONTROLLER_MODE, default=HVACMode.HEAT
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(HVACMode),
                translation_key="component.climate.selector.hvac_mode",
            )
        ),
        "section_fan": KNXSectionFlat(collapsible=True),
        vol.Optional(CONF_GA_FAN_SPEED): GASelector(dpt=ClimateFanSpeedMode),
        vol.Required(ClimateConf.FAN_MAX_STEP, default=3): AllSerializeFirst(
            selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=100, step=1)
            ),
            vol.Coerce(int),
        ),
        vol.Required(
            ClimateConf.FAN_ZERO_MODE, default=FanZeroMode.OFF
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(FanZeroMode),
                translation_key="component.knx.config_panel.entities.create.climate.knx.fan_zero_mode",
            )
        ),
        vol.Optional(CONF_GA_FAN_SWING): GASelector(valid_dpt="1"),
        vol.Optional(CONF_GA_FAN_SWING_HORIZONTAL): GASelector(valid_dpt="1"),
        vol.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
    },
)

KNX_SCHEMA_FOR_PLATFORM = {
    Platform.BINARY_SENSOR: BINARY_SENSOR_KNX_SCHEMA,
    Platform.CLIMATE: CLIMATE_KNX_SCHEMA,
    Platform.COVER: COVER_KNX_SCHEMA,
    Platform.LIGHT: LIGHT_KNX_SCHEMA,
    Platform.SWITCH: SWITCH_KNX_SCHEMA,
}

ENTITY_STORE_DATA_SCHEMA: VolSchemaType = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_PLATFORM): vol.All(
                vol.Coerce(Platform),
                vol.In(SUPPORTED_PLATFORMS_UI),
            ),
            vol.Required(CONF_DATA): dict,
        },
        extra=vol.ALLOW_EXTRA,
    ),
    cv.key_value_schemas(
        CONF_PLATFORM,
        {
            platform: vol.Schema(
                {
                    vol.Required(CONF_DATA): {
                        vol.Required(CONF_ENTITY): BASE_ENTITY_SCHEMA,
                        vol.Required(DOMAIN): knx_schema,
                    },
                },
                extra=vol.ALLOW_EXTRA,
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
