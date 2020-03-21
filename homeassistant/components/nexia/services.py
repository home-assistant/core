"""Services for nexia."""

import voluptuous as vol

from homeassistant.components.climate.const import ATTR_HUMIDITY
from homeassistant.const import ATTR_ENTITY_ID
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ATTR_AIRCLEANER_MODE,
    DOMAIN,
    SIGNAL_AIRCLEANER_SERVICE,
    SIGNAL_HUMIDIFY_SERVICE,
)

SERVICE_SET_AIRCLEANER_MODE = "set_aircleaner_mode"
SERVICE_SET_HUMIDIFY_SETPOINT = "set_humidify_setpoint"

SET_FAN_MIN_ON_TIME_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_AIRCLEANER_MODE): cv.string,
    }
)

SET_HUMIDITY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_HUMIDITY): vol.All(
            vol.Coerce(int), vol.Range(min=35, max=65)
        ),
    }
)


def register_climate_services(hass):
    """Register all climate services for nexia."""

    async def _humidify_set_service(service):
        async_dispatcher_send(hass, SIGNAL_HUMIDIFY_SERVICE, service.data)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HUMIDIFY_SETPOINT,
        _humidify_set_service,
        schema=SET_HUMIDITY_SCHEMA,
    )

    async def _aircleaner_set_service(service):
        async_dispatcher_send(hass, SIGNAL_AIRCLEANER_SERVICE, service.data)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_AIRCLEANER_MODE,
        _aircleaner_set_service,
        schema=SET_FAN_MIN_ON_TIME_SCHEMA,
    )
