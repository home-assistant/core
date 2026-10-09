"""Service registration for Prowl integration."""

import probatio

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import ATTR_PRIORITY, ATTR_URL, DOMAIN, PRIORITY_MAP

SERVICE_SEND_MESSAGE_SCHEMA = cv.make_entity_service_schema(
    {
        probatio.Optional(ATTR_TITLE): cv.string,
        probatio.Required(ATTR_MESSAGE): cv.string,
        probatio.Optional(ATTR_PRIORITY): probatio.In(list(PRIORITY_MAP)),
        probatio.Optional(ATTR_URL): cv.url,
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Prowl integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        entity_domain=NOTIFY_DOMAIN,
        schema=SERVICE_SEND_MESSAGE_SCHEMA,
        func="prowl_send_message",
    )
