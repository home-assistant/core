"""Support for Songpal-enabled (Sony) media devices."""

from enum import StrEnum

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class SongpalService(StrEnum):
    """Store keys for Songpal services."""

    SET_SOUND_SETTING = "set_sound_setting"


class SongpalServiceArgument(StrEnum):
    """Store keys for Songpal service arguments."""

    NAME = "name"
    VALUE = "value"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SongpalService.SET_SOUND_SETTING,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Required(SongpalServiceArgument.NAME): cv.string,
            probatio.Required(SongpalServiceArgument.VALUE): cv.string,
        },
        func="async_set_sound_setting",
    )
