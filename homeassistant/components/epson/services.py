"""Support for Epson projector."""

from __future__ import annotations

from epson_projector.const import CMODE_LIST_SET
import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import ATTR_CMODE, DOMAIN

SERVICE_SELECT_CMODE = "select_cmode"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SELECT_CMODE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={vol.Required(ATTR_CMODE): vol.All(cv.string, vol.Any(*CMODE_LIST_SET))},
        func=SERVICE_SELECT_CMODE,
    )
