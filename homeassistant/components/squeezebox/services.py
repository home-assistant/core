"""Support for interfacing to the SqueezeBox API."""

from enum import StrEnum

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class SqueezeboxService(StrEnum):
    """Store keys for Squeezebox services."""

    CALL_METHOD = "call_method"
    CALL_QUERY = "call_query"


class SqueezeboxServiceArgument(StrEnum):
    """Store keys for Squeezebox service arguments."""

    COMMAND = "command"
    PARAMETERS = "parameters"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SqueezeboxService.CALL_METHOD,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Required(SqueezeboxServiceArgument.COMMAND): cv.string,
            probatio.Optional(SqueezeboxServiceArgument.PARAMETERS): probatio.All(
                probatio.EnsureList(), probatio.NonEmpty(), [cv.string]
            ),
        },
        func="async_call_method",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SqueezeboxService.CALL_QUERY,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Required(SqueezeboxServiceArgument.COMMAND): cv.string,
            probatio.Optional(SqueezeboxServiceArgument.PARAMETERS): probatio.All(
                probatio.EnsureList(), probatio.NonEmpty(), [cv.string]
            ),
        },
        func="async_call_query",
    )
