"""Support for repeating alerts when conditions are met.

DEVELOPMENT OF THE ALERT INTEGRATION IS FROZEN.
"""

import probatio

from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_REPEAT,
    CONF_STATE,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ALERT_MESSAGE,
    CONF_CAN_ACK,
    CONF_DATA,
    CONF_DONE_MESSAGE,
    CONF_NOTIFIERS,
    CONF_SKIP_FIRST,
    CONF_TITLE,
    DEFAULT_CAN_ACK,
    DEFAULT_SKIP_FIRST,
    DOMAIN,
    LOGGER,
)
from .entity import AlertEntity

ALERT_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_NAME): cv.string,
        probatio.Required(CONF_ENTITY_ID): cv.entity_id,
        probatio.Optional(CONF_STATE, default=STATE_ON): cv.string,
        probatio.Required(CONF_REPEAT): probatio.All(
            cv.ensure_list,
            [probatio.Coerce(float)],
            # Minimum delay is 1 second = 0.016 minutes
            [probatio.Range(min=0.016)],
        ),
        probatio.Optional(CONF_CAN_ACK, default=DEFAULT_CAN_ACK): cv.boolean,
        probatio.Optional(CONF_SKIP_FIRST, default=DEFAULT_SKIP_FIRST): cv.boolean,
        probatio.Optional(CONF_ALERT_MESSAGE): cv.template,
        probatio.Optional(CONF_DONE_MESSAGE): cv.template,
        probatio.Optional(CONF_TITLE): cv.template,
        probatio.Optional(CONF_DATA): dict,
        probatio.Optional(CONF_NOTIFIERS, default=list): probatio.All(
            cv.ensure_list, [cv.string]
        ),
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {DOMAIN: cv.schema_with_slug_keys(ALERT_SCHEMA)}, extra=probatio.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Alert component.

    DEVELOPMENT OF THE ALERT INTEGRATION IS FROZEN.
    """
    component = EntityComponent[AlertEntity](LOGGER, DOMAIN, hass)

    entities: list[AlertEntity] = []

    for object_id, cfg in config[DOMAIN].items():
        if not cfg:
            cfg = {}

        name = cfg[CONF_NAME]
        watched_entity_id = cfg[CONF_ENTITY_ID]
        alert_state = cfg[CONF_STATE]
        repeat = cfg[CONF_REPEAT]
        skip_first = cfg[CONF_SKIP_FIRST]
        message_template = cfg.get(CONF_ALERT_MESSAGE)
        done_message_template = cfg.get(CONF_DONE_MESSAGE)
        notifiers = cfg[CONF_NOTIFIERS]
        can_ack = cfg[CONF_CAN_ACK]
        title_template = cfg.get(CONF_TITLE)
        data = cfg.get(CONF_DATA)

        entities.append(
            AlertEntity(
                hass,
                object_id,
                name,
                watched_entity_id,
                alert_state,
                repeat,
                skip_first,
                message_template,
                done_message_template,
                notifiers,
                can_ack,
                title_template,
                data,
            )
        )

    if not entities:
        return False

    component.async_register_entity_service(SERVICE_TURN_OFF, None, "async_turn_off")
    component.async_register_entity_service(SERVICE_TURN_ON, None, "async_turn_on")
    component.async_register_entity_service(SERVICE_TOGGLE, None, "async_toggle")

    await component.async_add_entities(entities)

    return True
