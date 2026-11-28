"""Support for the Roku media player."""

from enum import StrEnum

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN


class RokuService(StrEnum):
    """Store keys for Roku services."""

    SEARCH = "search"


class RokuServiceArgument(StrEnum):
    """Store keys for Roku service arguments."""

    KEYWORD = "keyword"


SEARCH_SCHEMA: VolDictType = {probatio.Required(RokuServiceArgument.KEYWORD): str}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        RokuService.SEARCH,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=SEARCH_SCHEMA,
        func="search",
    )
