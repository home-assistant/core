"""Services for the timer integration."""

import probatio

from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from .const import (
    DATA_TIMER,
    DEFAULT_DURATION,
    DOMAIN,
    TimerService,
    TimerServiceArgument,
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
        TimerService.RELOAD,
        _async_reload_service,
        schema=RELOAD_SERVICE_SCHEMA,
    )

    component = hass.data[DATA_TIMER].component
    component.async_register_entity_service(
        TimerService.START,
        {
            probatio.Optional(
                TimerServiceArgument.DURATION, default=DEFAULT_DURATION
            ): cv.time_period
        },
        "async_start",
    )
    component.async_register_entity_service(TimerService.PAUSE, None, "async_pause")
    component.async_register_entity_service(TimerService.CANCEL, None, "async_cancel")
    component.async_register_entity_service(TimerService.FINISH, None, "async_finish")
    component.async_register_entity_service(
        TimerService.CHANGE,
        {
            probatio.Optional(
                TimerServiceArgument.DURATION, default=DEFAULT_DURATION
            ): cv.time_period
        },
        "async_change",
    )
