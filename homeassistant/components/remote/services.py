"""Services for the Remote integration."""

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    DATA_COMPONENT,
    DEFAULT_HOLD_SECS,
    DEFAULT_NUM_REPEATS,
    DOMAIN,
    RemoteEntityFeature,
    RemoteNavigation,
    RemoteService,
    RemoteServiceArgument,
)
from .entity import RemoteEntity

REMOTE_SERVICE_ACTIVITY_SCHEMA = cv.make_entity_service_schema(
    {probatio.Optional(RemoteServiceArgument.ACTIVITY): cv.string}
)


async def _async_navigate(entity: RemoteEntity, call: ServiceCall) -> None:
    """Send a navigation action if the remote supports it."""
    direction: RemoteNavigation = call.data[RemoteServiceArgument.DIRECTION]
    if direction not in entity.supported_navigation:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="navigation_not_supported",
            translation_placeholders={
                "entity_id": entity.entity_id,
                "direction": direction,
            },
        )
    await entity.async_navigate(direction)


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
        RemoteService.NAVIGATE,
        {
            probatio.Required(RemoteServiceArgument.DIRECTION): probatio.Coerce(
                RemoteNavigation
            )
        },
        _async_navigate,
        [RemoteEntityFeature.NAVIGATE],
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
