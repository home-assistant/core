"""Services for the Channels integration."""

from enum import StrEnum

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN


class ChannelsService(StrEnum):
    """Store keys for Channels services."""

    SEEK_FORWARD = "seek_forward"
    SEEK_BACKWARD = "seek_backward"
    SEEK_BY = "seek_by"


class ChannelsServiceArgument(StrEnum):
    """Store keys for Channels service arguments."""

    SECONDS = "seconds"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Channels integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        ChannelsService.SEEK_FORWARD,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="seek_forward",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        ChannelsService.SEEK_BACKWARD,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="seek_backward",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        ChannelsService.SEEK_BY,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Required(ChannelsServiceArgument.SECONDS): probatio.Coerce(int)
        },
        func="seek_by",
    )
