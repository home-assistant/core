"""Services for the Select integration."""

import probatio

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import DATA_COMPONENT, SelectService, SelectServiceArgument


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the select services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SelectService.SELECT_FIRST,
        None,
        "async_first",
    )

    component.async_register_entity_service(
        SelectService.SELECT_LAST,
        None,
        "async_last",
    )

    component.async_register_entity_service(
        SelectService.SELECT_NEXT,
        {probatio.Optional(SelectServiceArgument.CYCLE, default=True): bool},
        "async_next",
    )

    component.async_register_entity_service(
        SelectService.SELECT_OPTION,
        {probatio.Required(SelectServiceArgument.OPTION): cv.string},
        "async_handle_select_option",
    )

    component.async_register_entity_service(
        SelectService.SELECT_PREVIOUS,
        {probatio.Optional(SelectServiceArgument.CYCLE, default=True): bool},
        "async_previous",
    )
