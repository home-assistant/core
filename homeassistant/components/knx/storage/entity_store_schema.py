"""KNX entity store schema."""

from enum import StrEnum, unique

import voluptuous as vol

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
    ColorTempModes,
    CoverConf,
)
from .const import (
    CONF_COLOR,
    CONF_COLOR_TEMP_MAX,
    CONF_COLOR_TEMP_MIN,
    CONF_DATA,
    CONF_DEVICE_INFO,
    CONF_ENTITY,
    CONF_GA_ANGLE,
    CONF_GA_BLUE_BRIGHTNESS,
    CONF_GA_BLUE_SWITCH,
    CONF_GA_BRIGHTNESS,
    CONF_GA_COLOR,
    CONF_GA_COLOR_TEMP,
    CONF_GA_GREEN_BRIGHTNESS,
    CONF_GA_GREEN_SWITCH,
    CONF_GA_HUE,
    CONF_GA_POSITION_SET,
    CONF_GA_POSITION_STATE,
    CONF_GA_RED_BRIGHTNESS,
    CONF_GA_RED_SWITCH,
    CONF_GA_SATURATION,
    CONF_GA_SENSOR,
    CONF_GA_STEP,
    CONF_GA_STOP,
    CONF_GA_SWITCH,
    CONF_GA_UP_DOWN,
    CONF_GA_WHITE_BRIGHTNESS,
    CONF_GA_WHITE_SWITCH,
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
        "section_binary_sensor": KNXSectionFlat(),
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
            "section_binary_control": KNXSectionFlat(),
            vol.Optional(CONF_GA_UP_DOWN): GASelector(state=False),
            vol.Optional(CoverConf.INVERT_UPDOWN): selector.BooleanSelector(),
            "section_stop_control": KNXSectionFlat(),
            vol.Optional(CONF_GA_STOP): GASelector(state=False),
            vol.Optional(CONF_GA_STEP): GASelector(state=False),
            "section_position_control": KNXSectionFlat(collapsible=True),
            vol.Optional(CONF_GA_POSITION_SET): GASelector(state=False),
            vol.Optional(CONF_GA_POSITION_STATE): GASelector(write=False),
            vol.Optional(CoverConf.INVERT_POSITION): selector.BooleanSelector(),
            "section_tilt_control": KNXSectionFlat(collapsible=True),
            vol.Optional(CONF_GA_ANGLE): GASelector(),
            vol.Optional(CoverConf.INVERT_ANGLE): selector.BooleanSelector(),
            "section_travel_time": KNXSectionFlat(),
            vol.Optional(
                CoverConf.TRAVELLING_TIME_UP, default=25
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=1000, step=0.1, unit_of_measurement="s"
                )
            ),
            vol.Optional(
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
            "section_switch": KNXSectionFlat(),
            vol.Optional(CONF_GA_SWITCH): GASelector(
                write_required=True, valid_dpt="1"
            ),
            "section_brightness": KNXSectionFlat(),
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
                        "section_red": KNXSectionFlat(),
                        vol.Optional(CONF_GA_RED_SWITCH): GASelector(
                            write_required=False, valid_dpt="1"
                        ),
                        vol.Required(CONF_GA_RED_BRIGHTNESS): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                        "section_green": KNXSectionFlat(),
                        vol.Optional(CONF_GA_GREEN_SWITCH): GASelector(
                            write_required=False, valid_dpt="1"
                        ),
                        vol.Required(CONF_GA_GREEN_BRIGHTNESS): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                        "section_blue": KNXSectionFlat(),
                        vol.Required(CONF_GA_BLUE_BRIGHTNESS): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                        vol.Optional(CONF_GA_BLUE_SWITCH): GASelector(
                            write_required=False, valid_dpt="1"
                        ),
                        "section_white": KNXSectionFlat(),
                        vol.Optional(CONF_GA_WHITE_BRIGHTNESS): GASelector(
                            write_required=True, valid_dpt="5.001"
                        ),
                        vol.Optional(CONF_GA_WHITE_SWITCH): GASelector(
                            write_required=False, valid_dpt="1"
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
        "section_switch": KNXSectionFlat(),
        vol.Required(CONF_GA_SWITCH): GASelector(write_required=True),
        vol.Optional(CONF_INVERT, default=False): selector.BooleanSelector(),
        vol.Optional(CONF_RESPOND_TO_READ, default=False): selector.BooleanSelector(),
        vol.Optional(CONF_SYNC_STATE, default=True): SyncStateSelector(),
    },
)

KNX_SCHEMA_FOR_PLATFORM = {
    Platform.BINARY_SENSOR: BINARY_SENSOR_KNX_SCHEMA,
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
