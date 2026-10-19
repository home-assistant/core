"""Services for the input_select integration."""

import probatio

from homeassistant.components.select import (
    ATTR_CYCLE,
    ATTR_OPTION,
    ATTR_OPTIONS,
    SERVICE_SELECT_FIRST,
    SERVICE_SELECT_LAST,
    SERVICE_SELECT_NEXT,
    SERVICE_SELECT_OPTION,
    SERVICE_SELECT_PREVIOUS,
)
from homeassistant.const import CONF_ID, SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from .const import DATA_INPUT_SELECT, DOMAIN, SERVICE_SET_OPTIONS

RELOAD_SERVICE_SCHEMA = probatio.Schema({})


async def _async_reload_service(service_call: ServiceCall) -> None:
    """Reload yaml entities."""
    hass = service_call.hass
    data = hass.data[DATA_INPUT_SELECT]
    conf = await data.component.async_prepare_reload(skip_reset=True)
    await data.yaml_collection.async_load(
        [{CONF_ID: id_, **(conf or {})} for id_, conf in conf.get(DOMAIN, {}).items()]
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the input_select services."""
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        _async_reload_service,
        schema=RELOAD_SERVICE_SCHEMA,
    )

    component = hass.data[DATA_INPUT_SELECT].component
    component.async_register_entity_service(SERVICE_SELECT_FIRST, None, "async_first")
    component.async_register_entity_service(SERVICE_SELECT_LAST, None, "async_last")
    component.async_register_entity_service(
        SERVICE_SELECT_NEXT,
        {probatio.Optional(ATTR_CYCLE, default=True): bool},
        "async_next",
    )
    component.async_register_entity_service(
        SERVICE_SELECT_OPTION,
        {probatio.Required(ATTR_OPTION): cv.string},
        "async_select_option",
    )
    component.async_register_entity_service(
        SERVICE_SELECT_PREVIOUS,
        {probatio.Optional(ATTR_CYCLE, default=True): bool},
        "async_previous",
    )
    component.async_register_entity_service(
        SERVICE_SET_OPTIONS,
        {
            probatio.Required(ATTR_OPTIONS): probatio.All(
                probatio.EnsureList(), probatio.NonEmpty(), [cv.string]
            )
        },
        "async_set_options",
    )
