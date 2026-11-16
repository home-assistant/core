"""Support for Openhome Devices."""

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN, OpenhomeService, OpenhomeServiceArgument


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        OpenhomeService.INVOKE_PIN,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={probatio.Required(OpenhomeServiceArgument.PIN): cv.positive_int},
        func="async_invoke_pin",
    )
