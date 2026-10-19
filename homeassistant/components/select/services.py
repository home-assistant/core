"""Services for the Select integration."""

import probatio

from homeassistant.const import ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CYCLE,
    DATA_COMPONENT,
    SERVICE_SELECT_FIRST,
    SERVICE_SELECT_LAST,
    SERVICE_SELECT_NEXT,
    SERVICE_SELECT_PREVIOUS,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the select services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SERVICE_SELECT_FIRST,
        None,
        "async_first",
    )

    component.async_register_entity_service(
        SERVICE_SELECT_LAST,
        None,
        "async_last",
    )

    component.async_register_entity_service(
        SERVICE_SELECT_NEXT,
        {probatio.Optional(ATTR_CYCLE, default=True): bool},
        "async_next",
    )

    component.async_register_entity_service(
        SERVICE_SELECT_OPTION,
        {probatio.Required(ATTR_OPTION): cv.string},
        "async_handle_select_option",
    )

    component.async_register_entity_service(
        SERVICE_SELECT_PREVIOUS,
        {probatio.Optional(ATTR_CYCLE, default=True): bool},
        "async_previous",
    )
