"""Service registration for Mobile App integration."""

import voluptuous as vol

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_platform_entity_service

from .const import DOMAIN


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Mobile App integration."""

    async_register_platform_entity_service(
        hass,
        DOMAIN,
        "dismiss_message",
        entity_domain=NOTIFY_DOMAIN,
        schema={vol.Required("tag"): cv.string},
        func="async_dismiss_message",
    )
