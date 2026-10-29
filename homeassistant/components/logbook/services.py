"""Services for the Activity integration."""

from enum import StrEnum

import probatio

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .helpers import async_log_entry


class LogbookService(StrEnum):
    """Store keys for logbook services."""

    LOG = "log"


class LogbookServiceArgument(StrEnum):
    """Store keys for logbook service arguments."""

    DOMAIN = "domain"
    MESSAGE = "message"
    NAME = "name"


LOG_MESSAGE_SCHEMA = probatio.Schema(
    {
        probatio.Required(LogbookServiceArgument.NAME): cv.string,
        probatio.Required(LogbookServiceArgument.MESSAGE): cv.string,
        probatio.Optional(LogbookServiceArgument.DOMAIN): cv.slug,
        probatio.Optional(ATTR_ENTITY_ID): cv.entity_id,
    }
)


@callback
def _log_message(service: ServiceCall) -> None:
    """Handle sending notification message service calls."""
    hass = service.hass
    message = service.data[LogbookServiceArgument.MESSAGE]
    name = service.data[LogbookServiceArgument.NAME]
    domain = service.data.get(LogbookServiceArgument.DOMAIN)
    entity_id = service.data.get(ATTR_ENTITY_ID)

    if entity_id is None and domain is None:
        # If there is no entity_id or
        # domain, the event will get filtered
        # away so we use the "logbook" domain
        domain = DOMAIN

    async_log_entry(hass, name, message, domain, entity_id, service.context)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Activity integration."""

    hass.services.async_register(
        DOMAIN, LogbookService.LOG, _log_message, schema=LOG_MESSAGE_SCHEMA
    )
