"""Service registratin for Mobile App integration."""

import voluptuous as vol

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_platform_entity_service

from .const import ATTR_TAG, DOMAIN, SERVICE_DISMISS_MESSAGE

SERVICE_DISMISS_NOTIFICATION_SCHEMA = cv.make_entity_service_schema(
    {vol.Required(ATTR_TAG): cv.string}
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Mobile App integration."""

    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_DISMISS_MESSAGE,
        entity_domain=NOTIFY_DOMAIN,
        schema=SERVICE_DISMISS_NOTIFICATION_SCHEMA,
        func="async_dismiss_message",
    )
