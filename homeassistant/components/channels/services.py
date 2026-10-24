"""Services for the Channels integration."""

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import ATTR_SECONDS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN, SERVICE_SEEK_BACKWARD, SERVICE_SEEK_BY, SERVICE_SEEK_FORWARD


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Channels integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SEEK_FORWARD,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="seek_forward",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SEEK_BACKWARD,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="seek_backward",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SEEK_BY,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={probatio.Required(ATTR_SECONDS): probatio.Coerce(int)},
        func="seek_by",
    )
