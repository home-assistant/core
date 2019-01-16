"""
Component to track utility consumption over given periods of time.

For more details about this component, please refer to the documentation
at https://www.home-assistant.io/components/utility_meter/
"""

import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import ATTR_ENTITY_ID
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from .const import (SIGNAL_START_PAUSE_METER, SIGNAL_RESET_METER)

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'utility_meter'

SERVICE_START_PAUSE = 'start_pause'
SERVICE_RESET = 'reset'

SERVICE_METER_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
})


async def async_setup(hass, config):
    """Set up an Utility Meter."""
    @callback
    def async_service_start_pause_meter(service):
        """Process service start_pause meter."""
        for entity in service.data[ATTR_ENTITY_ID]:
            dispatcher_send(hass, SIGNAL_START_PAUSE_METER, entity)

    @callback
    def async_service_reset_meter(service):
        """Process service reset meter."""
        for entity in service.data[ATTR_ENTITY_ID]:
            dispatcher_send(hass, SIGNAL_RESET_METER, entity)

    hass.services.async_register(DOMAIN, SERVICE_START_PAUSE,
                                 async_service_start_pause_meter,
                                 schema=SERVICE_METER_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_RESET,
                                 async_service_reset_meter,
                                 schema=SERVICE_METER_SCHEMA)

    return True
