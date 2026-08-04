"""Schema for KNX entity link configuration store."""

from typing import cast

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID, CONF_PLATFORM, Platform
from homeassistant.core import split_entity_id
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import VolSchemaType

from .const import CONF_GA_PASSIVE, CONF_GA_STATE, CONF_GA_WRITE
from .entity_link_controller import KNXEntityLinkStoreConfigModel
from .entity_store_validation import validate_config_store_data
from .knx_selector import GASelector

CONF_CHANNELS = "channels"

# Each channel maps directly to a group address group. The status group address (`write`)
# carries Home Assistant state to KNX; the command group addresses (`state`/`passive`) are
# listened on to drive the entity. The DPT is fixed per channel in `channel.py`, so
# `valid_dpt` only guides the frontend picker.
SWITCH_LINK_SCHEMA = vol.Schema(
    {
        vol.Required("switch"): GASelector(valid_dpt="1.001"),
    }
)

LINK_SCHEMA_FOR_PLATFORM: dict[Platform, VolSchemaType] = {
    Platform.SWITCH: SWITCH_LINK_SCHEMA,
}


def _validate_entity_domain(config: dict) -> dict:
    """Ensure the target entity_id belongs to the configured platform."""
    if split_entity_id(config[CONF_ENTITY_ID])[0] != config[CONF_PLATFORM]:
        raise vol.Invalid(
            f"entity_id {config[CONF_ENTITY_ID]} does not match"
            f" platform {config[CONF_PLATFORM]}",
            path=[CONF_ENTITY_ID],
        )
    return config


def _validate_distinct_gas(config: dict) -> dict:
    """A channel's status and command group addresses must differ (no self-loop)."""
    for role, ga in config[CONF_CHANNELS].items():
        status = ga.get(CONF_GA_WRITE)
        commands = {ga.get(CONF_GA_STATE), *ga.get(CONF_GA_PASSIVE, [])}
        commands.discard(None)
        if status is not None and status in commands:
            raise vol.Invalid(
                "status and command group addresses must differ",
                path=[CONF_CHANNELS, role],
            )
    return config


ENTITY_LINK_DATA_SCHEMA: VolSchemaType = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_PLATFORM): vol.All(
                vol.Coerce(Platform), vol.In(LINK_SCHEMA_FOR_PLATFORM)
            ),
            vol.Required(CONF_ENTITY_ID): cv.entity_id,
            vol.Required(CONF_CHANNELS): dict,
        },
        extra=vol.REMOVE_EXTRA,
    ),
    cv.key_value_schemas(
        CONF_PLATFORM,
        {
            platform: vol.Schema(
                {vol.Required(CONF_CHANNELS): channels_schema},
                extra=vol.ALLOW_EXTRA,
            )
            for platform, channels_schema in LINK_SCHEMA_FOR_PLATFORM.items()
        },
    ),
    _validate_entity_domain,
    _validate_distinct_gas,
)


def validate_entity_link_data(data: dict) -> KNXEntityLinkStoreConfigModel:
    """Validate entity link data.

    Return validated data or raise EntityStoreValidationException.
    """
    return cast(
        KNXEntityLinkStoreConfigModel,
        validate_config_store_data(ENTITY_LINK_DATA_SCHEMA, data),
    )
