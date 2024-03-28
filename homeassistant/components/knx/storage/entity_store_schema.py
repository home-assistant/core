"""KNX entity store schema."""

from enum import Enum, StrEnum, unique
from typing import Any

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ENTITY_CATEGORIES_SCHEMA

from ..const import SUPPORTED_PLATFORMS_UI, ColorTempModes
from ..validation import ga_validator, maybe_ga_validator, sync_state_validator

BASE_ENTITY_SCHEMA = vol.All(
    {
        vol.Optional("name", default=None): vol.Maybe(str),
        vol.Optional("device_info", default=None): vol.Maybe(str),
        vol.Optional("entity_category", default=None): vol.Any(
            ENTITY_CATEGORIES_SCHEMA, vol.SetTo(None)
        ),
    },
    vol.Any(
        vol.Schema(
            {
                vol.Required("name"): str,
            },
            extra=vol.ALLOW_EXTRA,
        ),
        vol.Schema(
            {
                vol.Required("device_info"): str,
            },
            extra=vol.ALLOW_EXTRA,
        ),
        msg="One of `Device` or `Name` is required",
    ),
)


def ga_schema(
    write: bool = True,
    state: bool = True,
    passive: bool = True,
    write_required: bool = False,
    state_required: bool = False,
    dpt: type[Enum] | None = None,
) -> vol.Schema:
    """Return a schema for a knx group address selector."""
    schema: dict[vol.Marker, Any] = {}

    def add_ga_item(key: str, allowed: bool, required: bool) -> None:
        """Add a group address item to the schema."""
        if not allowed:
            schema[vol.Remove(key)] = object
            return
        if required:
            schema[vol.Required(key)] = ga_validator
        else:
            schema[vol.Optional(key, default=None)] = maybe_ga_validator

    add_ga_item("write", write, write_required)
    add_ga_item("state", state, state_required)

    if passive:
        schema[vol.Optional("passive", default=list)] = vol.Any(
            [ga_validator],
            vol.All(  # Coerce `None` to an empty list if passive is allowed
                vol.IsFalse(), vol.SetTo(list)
            ),
        )
    else:
        schema[vol.Remove("passive")] = object

    if dpt is not None:
        schema[vol.Required("dpt")] = vol.In(dpt)
    else:
        schema[vol.Remove("dpt")] = object

    return vol.Schema(schema)


def optional_ga_schema(
    key: str, ga_schema_validator: vol.Schema
) -> dict[vol.Marker, vol.Schema]:
    """Validate group address schema or remove key if no address is set."""
    # frontend will return {key: {"write": None, "state": None}} for unused GA sets
    # -> remove this entirely for optional keys
    # if one GA is set, validate as usual
    return {
        vol.Optional(key): ga_schema_validator,
        vol.Remove(key): vol.Schema(
            {
                vol.Optional("write"): None,
                vol.Optional("state"): None,
                vol.Optional("passive"): vol.IsFalse(),  # None or empty list
            },
            extra=vol.ALLOW_EXTRA,
        ),
    }


SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required("entity"): BASE_ENTITY_SCHEMA,
        vol.Required("knx"): {
            vol.Optional("invert", default=False): bool,
            vol.Required("ga_switch"): ga_schema(write_required=True),
            vol.Optional("respond_to_read", default=False): bool,
            vol.Optional("sync_state", default=True): sync_state_validator,
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


_COMMON_LIGHT_SCHEMA = vol.Schema(
    {
        vol.Optional("sync_state", default=True): sync_state_validator,
        **optional_ga_schema(
            "ga_color_temp", ga_schema(write_required=True, dpt=ColorTempModes)
        ),
        vol.Optional("color_temp_min", default=2700): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Optional("color_temp_max", default=6000): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
    },
    extra=vol.REMOVE_EXTRA,
)

_DEFAULT_LIGHT_SCHEMA = _COMMON_LIGHT_SCHEMA.extend(
    {
        vol.Required("_light_color_mode_schema"): LightColorModeSchema.DEFAULT.value,
        vol.Required("ga_switch"): ga_schema(write_required=True),
        **optional_ga_schema("ga_brightness", ga_schema(write_required=True)),
        **optional_ga_schema(
            "ga_color",
            ga_schema(write_required=True, dpt=LightColorMode),
        ),
    }
)

_INDIVIDUAL_LIGHT_SCHEMA = _COMMON_LIGHT_SCHEMA.extend(
    {
        vol.Required("_light_color_mode_schema"): LightColorModeSchema.INDIVIDUAL.value,
        **optional_ga_schema("ga_switch", ga_schema(write_required=True)),
        **optional_ga_schema("ga_brightness", ga_schema(write_required=True)),
        vol.Required("ga_red_brightness"): ga_schema(write_required=True),
        **optional_ga_schema("ga_red_switch", ga_schema(write_required=False)),
        vol.Required("ga_green_brightness"): ga_schema(write_required=True),
        **optional_ga_schema("ga_green_switch", ga_schema(write_required=False)),
        vol.Required("ga_blue_brightness"): ga_schema(write_required=True),
        **optional_ga_schema("ga_blue_switch", ga_schema(write_required=False)),
        **optional_ga_schema("ga_white_brightness", ga_schema(write_required=True)),
        **optional_ga_schema("ga_white_switch", ga_schema(write_required=False)),
    }
)

_HSV_LIGHT_SCHEMA = _COMMON_LIGHT_SCHEMA.extend(
    {
        vol.Required("_light_color_mode_schema"): LightColorModeSchema.HSV.value,
        vol.Required("ga_switch"): ga_schema(write_required=True),
        vol.Required("ga_brightness"): ga_schema(write_required=True),
        vol.Required("ga_hue"): ga_schema(write_required=True),
        vol.Required("ga_saturation"): ga_schema(write_required=True),
    }
)


LIGHT_KNX_SCHEMA = cv.key_value_schemas(
    "_light_color_mode_schema",
    default_schema=_DEFAULT_LIGHT_SCHEMA,
    value_schemas={
        LightColorModeSchema.DEFAULT: _DEFAULT_LIGHT_SCHEMA,
        LightColorModeSchema.INDIVIDUAL: _INDIVIDUAL_LIGHT_SCHEMA,
        LightColorModeSchema.HSV: _HSV_LIGHT_SCHEMA,
    },
)

LIGHT_SCHEMA = vol.Schema(
    {
        vol.Required("entity"): BASE_ENTITY_SCHEMA,
        vol.Required("knx"): LIGHT_KNX_SCHEMA,
    }
)

ENTITY_STORE_DATA_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required("platform"): vol.All(
                vol.Coerce(Platform),
                vol.In(SUPPORTED_PLATFORMS_UI),
            ),
            vol.Required("data"): dict,
        },
        extra=vol.ALLOW_EXTRA,
    ),
    cv.key_value_schemas(
        "platform",
        {
            Platform.SWITCH: vol.Schema(
                {vol.Required("data"): SWITCH_SCHEMA}, extra=vol.ALLOW_EXTRA
            ),
            Platform.LIGHT: vol.Schema(
                {vol.Required("data"): LIGHT_SCHEMA}, extra=vol.ALLOW_EXTRA
            ),
        },
    ),
)

CREATE_ENTITY_BASE_SCHEMA = {
    vol.Required("platform"): str,
    vol.Required("data"): dict,  # validated by ENTITY_STORE_DATA_SCHEMA with vol.All()
}

UPDATE_ENTITY_BASE_SCHEMA = {
    vol.Required("unique_id"): str,
    **CREATE_ENTITY_BASE_SCHEMA,
}

SCHEMA_OPTIONS: dict[str, dict] = {}
