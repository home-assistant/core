"""Services for the timer integration."""

import probatio

from homeassistant.const import CONF_ID, SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from .const import (
    ATTR_DURATION,
    DATA_TIMER,
    DEFAULT_DURATION,
    DOMAIN,
    SERVICE_CANCEL,
    SERVICE_CHANGE,
    SERVICE_FINISH,
    SERVICE_PAUSE,
    SERVICE_START,
)

RELOAD_SERVICE_SCHEMA = probatio.Schema({})


async def _async_reload_service(service_call: ServiceCall) -> None:
    """Reload yaml entities."""
    hass = service_call.hass
    data = hass.data[DATA_TIMER]
    conf = await data.component.async_prepare_reload(skip_reset=True)
    await data.yaml_collection.async_load(
        [{CONF_ID: id_, **(conf or {})} for id_, conf in conf.get(DOMAIN, {}).items()]
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the timer services."""
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        _async_reload_service,
        schema=RELOAD_SERVICE_SCHEMA,
    )

    component = hass.data[DATA_TIMER].component
    component.async_register_entity_service(
        SERVICE_START,
        {probatio.Optional(ATTR_DURATION, default=DEFAULT_DURATION): cv.time_period},
        "async_start",
    )
    component.async_register_entity_service(SERVICE_PAUSE, None, "async_pause")
    component.async_register_entity_service(SERVICE_CANCEL, None, "async_cancel")
    component.async_register_entity_service(SERVICE_FINISH, None, "async_finish")
    component.async_register_entity_service(
        SERVICE_CHANGE,
        {probatio.Optional(ATTR_DURATION, default=DEFAULT_DURATION): cv.time_period},
        "async_change",
    )
