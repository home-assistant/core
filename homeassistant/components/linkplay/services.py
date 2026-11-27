"""Support for LinkPlay media players."""

from enum import StrEnum

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class LinkPlayService(StrEnum):
    """Store keys for LinkPlay services."""

    PLAY_PRESET = "play_preset"


class LinkPlayServiceArgument(StrEnum):
    """Store keys for LinkPlay service arguments."""

    PRESET_NUMBER = "preset_number"


SERVICE_PLAY_PRESET_SCHEMA = cv.make_entity_service_schema(
    {
        probatio.Required(LinkPlayServiceArgument.PRESET_NUMBER): cv.positive_int,
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        LinkPlayService.PLAY_PRESET,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=SERVICE_PLAY_PRESET_SCHEMA,
        func="async_play_preset",
    )
