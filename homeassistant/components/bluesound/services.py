"""Services for the Bluesound integration."""

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import ATTR_MASTER, DOMAIN, SERVICE_JOIN, SERVICE_UNJOIN


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Bluesound integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_JOIN,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={probatio.Required(ATTR_MASTER): cv.entity_id},
        func="async_bluesound_join",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_UNJOIN,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="async_bluesound_unjoin",
    )
