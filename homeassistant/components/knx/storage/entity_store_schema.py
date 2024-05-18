"""KNX entity store schema."""

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ENTITY_CATEGORIES_SCHEMA

from ..const import SUPPORTED_PLATFORMS_UI
from ..validation import sync_state_validator
from .knx_selector import GASelector

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


def optional_ga_schema(
    key: str, ga_selector: GASelector
) -> dict[vol.Marker, vol.Schema]:
    """Validate group address schema or remove key if no address is set."""
    # frontend will return {key: {"write": None, "state": None}} for unused GA sets
    # -> remove this entirely for optional keys
    # if one GA is set, validate as usual
    return {
        vol.Optional(key): ga_selector,
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
            vol.Required("ga_switch"): GASelector(write_required=True),
            vol.Optional("respond_to_read", default=False): bool,
            vol.Optional("sync_state", default=True): sync_state_validator,
        },
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
        },
    ),
)

CREATE_ENTITY_BASE_SCHEMA = {
    vol.Required("platform"): str,
    vol.Required("data"): dict,  # validated by ENTITY_STORE_DATA_SCHEMA for platform
}

UPDATE_ENTITY_BASE_SCHEMA = {
    vol.Required("entity_id"): str,
    **CREATE_ENTITY_BASE_SCHEMA,
}
