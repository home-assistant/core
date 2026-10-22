"""Services for the Remote integration."""

import probatio

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    DATA_COMPONENT,
    DEFAULT_HOLD_SECS,
    DEFAULT_NUM_REPEATS,
    RemoteService,
    RemoteServiceArgument,
)

REMOTE_SERVICE_ACTIVITY_SCHEMA = cv.make_entity_service_schema(
    {probatio.Optional(RemoteServiceArgument.ACTIVITY): cv.string}
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the remote services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        RemoteService.TURN_OFF, REMOTE_SERVICE_ACTIVITY_SCHEMA, "async_turn_off"
    )

    component.async_register_entity_service(
        RemoteService.TURN_ON, REMOTE_SERVICE_ACTIVITY_SCHEMA, "async_turn_on"
    )

    component.async_register_entity_service(
        RemoteService.TOGGLE, REMOTE_SERVICE_ACTIVITY_SCHEMA, "async_toggle"
    )

    component.async_register_entity_service(
        RemoteService.SEND_COMMAND,
        {
            probatio.Required(RemoteServiceArgument.COMMAND): probatio.All(
                probatio.EnsureList(), [cv.string]
            ),
            probatio.Optional(RemoteServiceArgument.DEVICE): cv.string,
            probatio.Optional(
                RemoteServiceArgument.NUM_REPEATS, default=DEFAULT_NUM_REPEATS
            ): cv.positive_int,
            probatio.Optional(RemoteServiceArgument.DELAY_SECS): probatio.Coerce(float),
            probatio.Optional(
                RemoteServiceArgument.HOLD_SECS, default=DEFAULT_HOLD_SECS
            ): probatio.Coerce(float),
        },
        "async_send_command",
    )

    component.async_register_entity_service(
        RemoteService.LEARN_COMMAND,
        {
            probatio.Optional(RemoteServiceArgument.DEVICE): cv.string,
            probatio.Optional(RemoteServiceArgument.COMMAND): probatio.All(
                probatio.EnsureList(), [cv.string]
            ),
            probatio.Optional(RemoteServiceArgument.COMMAND_TYPE): cv.string,
            probatio.Optional(RemoteServiceArgument.ALTERNATIVE): cv.boolean,
            probatio.Optional(RemoteServiceArgument.TIMEOUT): cv.positive_int,
        },
        "async_learn_command",
    )

    component.async_register_entity_service(
        RemoteService.DELETE_COMMAND,
        {
            probatio.Required(RemoteServiceArgument.COMMAND): probatio.All(
                probatio.EnsureList(), [cv.string]
            ),
            probatio.Optional(RemoteServiceArgument.DEVICE): cv.string,
        },
        "async_delete_command",
    )
