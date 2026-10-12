"""Services for the input_button integration."""

import probatio

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import CONF_ID, SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.service import async_register_admin_service

from .const import DATA_INPUT_BUTTON, DOMAIN

RELOAD_SERVICE_SCHEMA = probatio.Schema({})


async def _async_reload_service(service_call: ServiceCall) -> None:
    """Remove all input buttons and load new ones from config."""
    hass = service_call.hass
    data = hass.data[DATA_INPUT_BUTTON]
    conf = await data.component.async_prepare_reload(skip_reset=True)
    await data.yaml_collection.async_load(
        [{CONF_ID: id_, **(conf or {})} for id_, conf in conf.get(DOMAIN, {}).items()]
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the input_button services."""
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        _async_reload_service,
        schema=RELOAD_SERVICE_SCHEMA,
    )

    hass.data[DATA_INPUT_BUTTON].component.async_register_entity_service(
        SERVICE_PRESS, None, "_async_press_action"
    )
