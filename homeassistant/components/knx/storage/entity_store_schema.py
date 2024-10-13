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
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ENTITY_CATEGORIES_SCHEMA
from homeassistant.helpers.typing import VolDictType, VolSchemaType

from ..const import (
    CONF_INVERT,
    CONF_RESPOND_TO_READ,
    CONF_SYNC_STATE,
    DOMAIN,
    SUPPORTED_PLATFORMS_UI,
    ColorTempModes,
)
from ..validation import sync_state_validator
from .const import (
    CONF_COLOR_TEMP_MAX,
    CONF_COLOR_TEMP_MIN,
    CONF_DATA,
    CONF_DEVICE_INFO,
    CONF_ENTITY,
    CONF_GA_BLUE_BRIGHTNESS,
    CONF_GA_BLUE_SWITCH,
    CONF_GA_BRIGHTNESS,
    CONF_GA_COLOR,
    CONF_GA_COLOR_TEMP,
    CONF_GA_GREEN_BRIGHTNESS,
    CONF_GA_GREEN_SWITCH,
    CONF_GA_HUE,
    CONF_GA_PASSIVE,
    CONF_GA_RED_BRIGHTNESS,
    CONF_GA_RED_SWITCH,
    CONF_GA_SATURATION,
    CONF_GA_STATE,
    CONF_GA_SWITCH,
    CONF_GA_WHITE_BRIGHTNESS,
    CONF_GA_WHITE_SWITCH,
    CONF_GA_WRITE,
)
from .knx_selector import GASelector

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


def optional_ga_schema(key: str, ga_selector: GASelector) -> VolDictType:
    """Validate group address schema or remove key if no address is set."""
    # frontend will return {key: {"write": None, "state": None}} for unused GA sets
    # -> remove this entirely for optional keys
    # if one GA is set, validate as usual
    return {
        vol.Optional(key): ga_selector,
        vol.Remove(key): vol.Schema(
            {
                vol.Optional(CONF_GA_WRITE): None,
                vol.Optional(CONF_GA_STATE): None,
                vol.Optional(CONF_GA_PASSIVE): vol.IsFalse(),  # None or empty list
            },
            extra=vol.ALLOW_EXTRA,
        ),
    }


SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY): BASE_ENTITY_SCHEMA,
        vol.Required(DOMAIN): {
            vol.Optional(CONF_INVERT, default=False): bool,
            vol.Required(CONF_GA_SWITCH): GASelector(write_required=True),
            vol.Optional(CONF_RESPOND_TO_READ, default=False): bool,
            vol.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
        },
    }
)


@unique
class LightColorMode(StrEnum):
    """Enum for light color mode."""

    RGB = "232.600"
    RGBW = "251.600"
    XYY = "242.600"


@unique
class LightColorModeSchema(StrEnum):
    """Enum for light color mode."""

    DEFAULT = "default"
    INDIVIDUAL = "individual"
    HSV = "hsv"


_LIGHT_COLOR_MODE_SCHEMA = "_light_color_mode_schema"

_COMMON_LIGHT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
        **optional_ga_schema(
            CONF_GA_COLOR_TEMP, GASelector(write_required=True, dpt=ColorTempModes)
        ),
        vol.Optional(CONF_COLOR_TEMP_MIN, default=2700): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Optional(CONF_COLOR_TEMP_MAX, default=6000): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
    },
    extra=vol.REMOVE_EXTRA,
)

_DEFAULT_LIGHT_SCHEMA = _COMMON_LIGHT_SCHEMA.extend(
    {
        vol.Required(_LIGHT_COLOR_MODE_SCHEMA): LightColorModeSchema.DEFAULT.value,
        vol.Required(CONF_GA_SWITCH): GASelector(write_required=True),
        **optional_ga_schema(CONF_GA_BRIGHTNESS, GASelector(write_required=True)),
        **optional_ga_schema(
            CONF_GA_COLOR,
            GASelector(write_required=True, dpt=LightColorMode),
        ),
    }
)

_INDIVIDUAL_LIGHT_SCHEMA = _COMMON_LIGHT_SCHEMA.extend(
    {
        vol.Required(_LIGHT_COLOR_MODE_SCHEMA): LightColorModeSchema.INDIVIDUAL.value,
        **optional_ga_schema(CONF_GA_SWITCH, GASelector(write_required=True)),
        **optional_ga_schema(CONF_GA_BRIGHTNESS, GASelector(write_required=True)),
        vol.Required(CONF_GA_RED_BRIGHTNESS): GASelector(write_required=True),
        **optional_ga_schema(CONF_GA_RED_SWITCH, GASelector(write_required=False)),
        vol.Required(CONF_GA_GREEN_BRIGHTNESS): GASelector(write_required=True),
        **optional_ga_schema(CONF_GA_GREEN_SWITCH, GASelector(write_required=False)),
        vol.Required(CONF_GA_BLUE_BRIGHTNESS): GASelector(write_required=True),
        **optional_ga_schema(CONF_GA_BLUE_SWITCH, GASelector(write_required=False)),
        **optional_ga_schema(CONF_GA_WHITE_BRIGHTNESS, GASelector(write_required=True)),
        **optional_ga_schema(CONF_GA_WHITE_SWITCH, GASelector(write_required=False)),
    }
)

_HSV_LIGHT_SCHEMA = _COMMON_LIGHT_SCHEMA.extend(
    {
        vol.Required(_LIGHT_COLOR_MODE_SCHEMA): LightColorModeSchema.HSV.value,
        vol.Required(CONF_GA_SWITCH): GASelector(write_required=True),
        vol.Required(CONF_GA_BRIGHTNESS): GASelector(write_required=True),
        vol.Required(CONF_GA_HUE): GASelector(write_required=True),
        vol.Required(CONF_GA_SATURATION): GASelector(write_required=True),
    }
)


LIGHT_KNX_SCHEMA = cv.key_value_schemas(
    _LIGHT_COLOR_MODE_SCHEMA,
    default_schema=_DEFAULT_LIGHT_SCHEMA,
    value_schemas={
        LightColorModeSchema.DEFAULT: _DEFAULT_LIGHT_SCHEMA,
        LightColorModeSchema.INDIVIDUAL: _INDIVIDUAL_LIGHT_SCHEMA,
        LightColorModeSchema.HSV: _HSV_LIGHT_SCHEMA,
    },
)

LIGHT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY): BASE_ENTITY_SCHEMA,
        vol.Required(DOMAIN): LIGHT_KNX_SCHEMA,
    }
)

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
            Platform.SWITCH: vol.Schema(
                {vol.Required(CONF_DATA): SWITCH_SCHEMA}, extra=vol.ALLOW_EXTRA
            ),
            Platform.LIGHT: vol.Schema(
                {vol.Required("data"): LIGHT_SCHEMA}, extra=vol.ALLOW_EXTRA
            ),
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
