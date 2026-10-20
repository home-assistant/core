"""Services for the automation integration."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.const import SERVICE_TOGGLE, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_VARIABLES,
    CONF_SKIP_CONDITION,
    CONF_STOP_ACTIONS,
    DATA_COMPONENT,
    DEFAULT_STOP_ACTIONS,
    SERVICE_TRIGGER,
)

if TYPE_CHECKING:
    from .entity import BaseAutomationEntity


async def _trigger_service_handler(
    entity: BaseAutomationEntity, service_call: ServiceCall
) -> None:
    """Handle forced automation trigger, e.g. from frontend."""
    await entity.async_trigger(
        {**service_call.data[ATTR_VARIABLES], "trigger": {"platform": None}},
        skip_condition=service_call.data[CONF_SKIP_CONDITION],
        context=service_call.context,
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the automation integration."""
    component = hass.data[DATA_COMPONENT]
    component.async_register_entity_service(
        SERVICE_TRIGGER,
        {
            probatio.Optional(ATTR_VARIABLES, default={}): dict,
            probatio.Optional(CONF_SKIP_CONDITION, default=True): bool,
        },
        _trigger_service_handler,
    )
    component.async_register_entity_service(SERVICE_TOGGLE, None, "async_toggle")
    component.async_register_entity_service(SERVICE_TURN_ON, None, "async_turn_on")
    component.async_register_entity_service(
        SERVICE_TURN_OFF,
        {
            probatio.Optional(
                CONF_STOP_ACTIONS, default=DEFAULT_STOP_ACTIONS
            ): cv.boolean
        },
        "async_turn_off",
    )
