"""KNX entity store schema."""
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
    send: bool = True,
    read: bool = True,
    passive: bool = True,
    send_required: bool = False,
    read_required: bool = False,
) -> vol.Schema:
    """Return a schema for a knx group address selector."""
    schema = {}
    _send_marker = vol.Required if send and send_required else vol.Optional
    schema[_send_marker("send", default=None)] = (
        None if not read else ga_validator if send_required else vol.Maybe(ga_validator)
    )
    _read_marker = vol.Required if read and read_required else vol.Optional
    schema[_read_marker("read", default=None)] = (
        None if not read else ga_validator if read_required else vol.Maybe(ga_validator)
    )
    schema[vol.Optional("passive", default=None)] = vol.All(
        vol.Maybe([ga_validator]) if passive else vol.Any(None, []),
        vol.Any(  # Coerce `None` to an empty list if passive is allowed
            vol.IsTrue(), vol.SetTo([])
        ),
    )
    return vol.Schema(schema)


SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required("entity"): BASE_ENTITY_SCHEMA,
        vol.Optional("invert", default=False): bool,
        vol.Required("ga_switch"): ga_schema(send_required=True),
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
