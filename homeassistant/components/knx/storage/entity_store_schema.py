"""KNX entity store schema."""
from typing import Any

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ENTITY_CATEGORIES_SCHEMA

from ..validation import ga_validator, sync_state_validator

BASE_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Optional("name", default=None): vol.Maybe(str),
        vol.Optional("device_info", default=None): vol.Maybe(str),
        vol.Optional("entity_category", default=None): vol.Any(
            ENTITY_CATEGORIES_SCHEMA, vol.SetTo(None)
        ),
    }
)


def ga_schema(
    write: bool = True,
    state: bool = True,
    passive: bool = True,
    write_required: bool = False,
    state_required: bool = False,
) -> vol.Schema:
    """Return a schema for a knx group address selector."""
    schema: dict[vol.Marker, Any] = {}
    if write:
        schema |= (
            {vol.Required("write"): ga_validator}
            if write_required
            else {vol.Optional("write", default=None): vol.Maybe(ga_validator)}
        )
    else:
        schema[vol.Remove("write")] = object
    if state:
        schema |= (
            {vol.Required("state"): ga_validator}
            if state_required
            else {vol.Optional("state", default=None): vol.Maybe(ga_validator)}
        )
    else:
        schema[vol.Remove("state")] = object
    if passive:
        schema[vol.Optional("passive", default=list)] = vol.Any(
            [ga_validator],
            vol.All(  # Coerce `None` to an empty list if passive is allowed
                vol.IsFalse(), vol.SetTo(list)
            ),
        )
    else:
        schema[vol.Remove("passive")] = object
    return vol.Schema(schema)


SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required("entity"): BASE_ENTITY_SCHEMA,
        vol.Optional("invert", default=False): bool,
        vol.Required("ga_switch"): ga_schema(write_required=True),
        vol.Optional("respond_to_read", default=False): bool,
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
