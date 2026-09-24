"""Services for the Remote integration."""

import probatio

from homeassistant.const import (
    ATTR_COMMAND,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_ACTIVITY,
    ATTR_ALTERNATIVE,
    ATTR_COMMAND_TYPE,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_HOLD_SECS,
    ATTR_NUM_REPEATS,
    ATTR_TIMEOUT,
    DATA_COMPONENT,
    DEFAULT_HOLD_SECS,
    DEFAULT_NUM_REPEATS,
    SERVICE_DELETE_COMMAND,
    SERVICE_LEARN_COMMAND,
    SERVICE_SEND_COMMAND,
)

REMOTE_SERVICE_ACTIVITY_SCHEMA = cv.make_entity_service_schema(
    {probatio.Optional(ATTR_ACTIVITY): cv.string}
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the remote services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SERVICE_TURN_OFF, REMOTE_SERVICE_ACTIVITY_SCHEMA, "async_turn_off"
    )

    component.async_register_entity_service(
        SERVICE_TURN_ON, REMOTE_SERVICE_ACTIVITY_SCHEMA, "async_turn_on"
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE, REMOTE_SERVICE_ACTIVITY_SCHEMA, "async_toggle"
    )

    component.async_register_entity_service(
        SERVICE_SEND_COMMAND,
        {
            probatio.Required(ATTR_COMMAND): probatio.All(cv.ensure_list, [cv.string]),
            probatio.Optional(ATTR_DEVICE): cv.string,
            probatio.Optional(
                ATTR_NUM_REPEATS, default=DEFAULT_NUM_REPEATS
            ): cv.positive_int,
            probatio.Optional(ATTR_DELAY_SECS): probatio.Coerce(float),
            probatio.Optional(
                ATTR_HOLD_SECS, default=DEFAULT_HOLD_SECS
            ): probatio.Coerce(float),
        },
        "async_send_command",
    )

    component.async_register_entity_service(
        SERVICE_LEARN_COMMAND,
        {
            probatio.Optional(ATTR_DEVICE): cv.string,
            probatio.Optional(ATTR_COMMAND): probatio.All(cv.ensure_list, [cv.string]),
            probatio.Optional(ATTR_COMMAND_TYPE): cv.string,
            probatio.Optional(ATTR_ALTERNATIVE): cv.boolean,
            probatio.Optional(ATTR_TIMEOUT): cv.positive_int,
        },
        "async_learn_command",
    )

    component.async_register_entity_service(
        SERVICE_DELETE_COMMAND,
        {
            probatio.Required(ATTR_COMMAND): probatio.All(cv.ensure_list, [cv.string]),
            probatio.Optional(ATTR_DEVICE): cv.string,
        },
        "async_delete_command",
    )
