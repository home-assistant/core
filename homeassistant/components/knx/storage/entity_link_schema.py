"""Schema for KNX entity link configuration store."""

import probatio

from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.core import split_entity_id
from homeassistant.helpers import config_validation as cv, selector

from ..const import CONF_INVERT, CONF_RESPOND_TO_READ
from .const import (
    CONF_COOLDOWN,
    CONF_DATA,
    CONF_GA_COMMAND,
    CONF_GA_PASSIVE,
    CONF_GA_STATE,
    CONF_GA_STATUS,
    CONF_GA_WRITE,
    CONF_KNX,
    CONF_NOTES,
    CONF_PERIODIC_SEND,
    CONF_SEND_ON_INIT,
)
from .entity_link_controller import KNXEntityLinkDataModel
from .entity_store_validation import validate_config_store_data
from .knx_selector import GASelector, KNXSectionFlat

# A link makes Home Assistant act as the KNX actuator, so the group address roles are the
# mirror image of a KNX entity: `ga_status` carries the entity state to the bus (HA -> KNX)
# and `ga_command` is listened on to drive the entity (KNX -> HA).
SWITCH_LINK_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_GA_STATUS): GASelector(
            write_required=True, state=False, passive=False, valid_dpt="1.001"
        ),
        probatio.Required(CONF_GA_COMMAND): GASelector(
            write=False, state_required=True, valid_dpt="1.001"
        ),
        probatio.Optional(CONF_INVERT, default=False): selector.BooleanSelector(),
        probatio.Optional(
            CONF_RESPOND_TO_READ, default=True
        ): selector.BooleanSelector(),
        "section_advanced_options": KNXSectionFlat(collapsible=True),
        probatio.Optional(CONF_SEND_ON_INIT, default=True): selector.BooleanSelector(),
        probatio.Optional(CONF_COOLDOWN, default=0.0): cv.positive_float,
        probatio.Optional(CONF_PERIODIC_SEND, default=0.0): cv.positive_float,
    }
)

LINK_SCHEMA_FOR_PLATFORM: dict[Platform, probatio.Schema] = {
    Platform.SWITCH: SWITCH_LINK_SCHEMA,
}


def link_platform_for_entity(entity_id: str) -> Platform | None:
    """Return the link-capable platform of an entity_id, or None."""
    try:
        platform = Platform(split_entity_id(entity_id)[0])
    except ValueError:
        return None
    return platform if platform in LINK_SCHEMA_FOR_PLATFORM else None


def _validate_platform_schema(config: dict) -> dict:
    """Validate the KNX section against the schema of the entity's platform."""
    entity_id = config[CONF_ENTITY_ID]
    platform = link_platform_for_entity(entity_id)
    if platform is None:
        raise probatio.Invalid(
            f"Entity links are not supported for {entity_id}",
            path=[CONF_ENTITY_ID],
        )
    config[CONF_DATA][CONF_KNX] = LINK_SCHEMA_FOR_PLATFORM[platform](
        config[CONF_DATA][CONF_KNX]
    )
    return config


def _validate_distinct_gas(config: dict) -> dict:
    """Status and command group addresses must differ (no self-loop)."""
    knx_config = config[CONF_DATA][CONF_KNX]
    command = knx_config[CONF_GA_COMMAND]
    commands = {command[CONF_GA_STATE], *command[CONF_GA_PASSIVE]}
    commands.discard(None)
    if knx_config[CONF_GA_STATUS][CONF_GA_WRITE] in commands:
        raise probatio.Invalid(
            "status and command group addresses must differ",
            path=[CONF_DATA, CONF_KNX, CONF_GA_COMMAND],
        )
    return config


ENTITY_LINK_CONFIG_SCHEMA = probatio.All(
    probatio.Schema(
        {
            probatio.Required(CONF_ENTITY_ID): selector.EntitySelector(),
            probatio.Required(CONF_DATA): probatio.Schema(
                {
                    probatio.Required(CONF_KNX): dict,
                    probatio.Optional(CONF_NOTES): str,
                },
                extra=probatio.REMOVE_EXTRA,
            ),
        },
        extra=probatio.REMOVE_EXTRA,
    ),
    _validate_platform_schema,
    _validate_distinct_gas,
)


def validate_entity_link_data(data: dict) -> KNXEntityLinkDataModel:
    """Validate entity link data.

    Return validated data or raise EntityStoreValidationException.
    """
    return validate_config_store_data(ENTITY_LINK_CONFIG_SCHEMA, data)  # type: ignore[return-value]
