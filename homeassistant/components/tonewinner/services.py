"""Services for the Tonewinner integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import ATTR_COMMAND
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_SEND_RAW = "send_raw"
SERVICE_SEND_RAW_FIELDS: dict[str | vol.Marker, Any] = {
    vol.Required(ATTR_COMMAND): cv.string,
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Tonewinner integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SEND_RAW,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=SERVICE_SEND_RAW_FIELDS,
        func="send_raw_command",
    )
