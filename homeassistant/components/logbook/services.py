"""Services for the Activity integration."""

import probatio

from homeassistant.const import ATTR_DOMAIN, ATTR_ENTITY_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import ATTR_MESSAGE, DOMAIN
from .helpers import async_log_entry

LOG_MESSAGE_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_NAME): cv.string,
        probatio.Required(ATTR_MESSAGE): cv.string,
        probatio.Optional(ATTR_DOMAIN): cv.slug,
        probatio.Optional(ATTR_ENTITY_ID): cv.entity_id,
    }
)


@callback
def _log_message(service: ServiceCall) -> None:
    """Handle sending notification message service calls."""
    hass = service.hass
    message = service.data[ATTR_MESSAGE]
    name = service.data[ATTR_NAME]
    domain = service.data.get(ATTR_DOMAIN)
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

    hass.services.async_register(DOMAIN, "log", _log_message, schema=LOG_MESSAGE_SCHEMA)
