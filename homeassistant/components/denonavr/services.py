"""Support for Denon AVR receivers using their HTTP interface."""

from enum import StrEnum

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class DenonAvrService(StrEnum):
    """Store keys for Denon AVR services."""

    GET_COMMAND = "get_command"
    SET_DYNAMIC_EQ = "set_dynamic_eq"
    UPDATE_AUDYSSEY = "update_audyssey"


class DenonAvrServiceArgument(StrEnum):
    """Store keys for Denon AVR service arguments."""

    COMMAND = "command"
    DYNAMIC_EQ = "dynamic_eq"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        DenonAvrService.GET_COMMAND,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={probatio.Required(DenonAvrServiceArgument.COMMAND): cv.string},
        func="async_get_command",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        DenonAvrService.SET_DYNAMIC_EQ,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={probatio.Required(DenonAvrServiceArgument.DYNAMIC_EQ): cv.boolean},
        func="async_set_dynamic_eq",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        DenonAvrService.UPDATE_AUDYSSEY,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="async_update_audyssey",
    )
