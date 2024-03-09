"""KNX entity store schema."""
from enum import Enum
from typing import Any

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ENTITY_CATEGORIES_SCHEMA

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
        vol.Optional("sync_state", default=True): sync_state_validator,
    }
)

ENTITY_STORE_DATA_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required("platform"): vol.Coerce(Platform),
            vol.Required("data"): dict,
        },
        extra=vol.ALLOW_EXTRA,
    ),
    cv.key_value_schemas(
        "platform",
        {
            Platform.SWITCH: vol.Schema(
                {vol.Required("data"): SWITCH_SCHEMA}, extra=vol.ALLOW_EXTRA
            )
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
