"""Services for the input_text integration."""

import probatio

from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from .const import DATA_INPUT_TEXT, DOMAIN, InputTextService, InputTextServiceArgument

RELOAD_SERVICE_SCHEMA = probatio.Schema({})


async def _async_reload_service(service_call: ServiceCall) -> None:
    """Reload yaml entities."""
    hass = service_call.hass
    data = hass.data[DATA_INPUT_TEXT]
    conf = await data.component.async_prepare_reload(skip_reset=True)
    await data.yaml_collection.async_load(
        [{CONF_ID: id_, **(cfg or {})} for id_, cfg in conf.get(DOMAIN, {}).items()]
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the input_text services."""
    async_register_admin_service(
        hass,
        DOMAIN,
        InputTextService.RELOAD,
        _async_reload_service,
        schema=RELOAD_SERVICE_SCHEMA,
    )

    hass.data[DATA_INPUT_TEXT].component.async_register_entity_service(
        InputTextService.SET_VALUE,
        {probatio.Required(InputTextServiceArgument.VALUE): cv.string},
        "async_set_value",
    )
