"""The snapcast component."""

import asyncio
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

DOMAIN = "snapcast"

SERVICE_SNAPSHOT = "snapshot"
SERVICE_RESTORE = "restore"
SERVICE_JOIN = "join"
SERVICE_UNJOIN = "unjoin"

ATTR_MASTER = "master"

SERVICE_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_ids})

JOIN_SERVICE_SCHEMA = SERVICE_SCHEMA.extend({vol.Required(ATTR_MASTER): cv.entity_id})


async def async_setup(hass, config):
    """Handle service configuration."""
    service_event = asyncio.Event()

    async def service_handle(service):
        """Dispatch a service call."""
        service_event.clear()
        async_dispatcher_send(
            hass, DOMAIN, service_event, service.service, service.data
        )
        await service_event.wait()

    hass.services.async_register(
        DOMAIN, SERVICE_SNAPSHOT, service_handle, schema=SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RESTORE, service_handle, schema=SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_JOIN, service_handle, schema=JOIN_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_UNJOIN, service_handle, schema=SERVICE_SCHEMA
    )

    return True
