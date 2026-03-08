"""Support for the Roku media player."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN

ATTR_KEYWORD = "keyword"

SERVICE_SEARCH = "search"

SEARCH_SCHEMA: VolDictType = {vol.Required(ATTR_KEYWORD): str}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SEARCH,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=SEARCH_SCHEMA,
        func="search",
    )
