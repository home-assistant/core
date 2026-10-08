"""Services for the Yamaha Network Receivers integration."""

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import (
    DOMAIN,
    SERVICE_ENABLE_OUTPUT,
    SERVICE_MENU_CURSOR,
    SERVICE_SELECT_SCENE,
)
from .media_player import CURSOR_TYPE_MAP

ATTR_CURSOR = "cursor"
ATTR_ENABLED = "enabled"
ATTR_PORT = "port"
ATTR_SCENE = "scene"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Yamaha Network Receivers integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SELECT_SCENE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={probatio.Required(ATTR_SCENE): cv.string},
        func="set_scene",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ENABLE_OUTPUT,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Required(ATTR_ENABLED): cv.boolean,
            probatio.Required(ATTR_PORT): cv.string,
        },
        func="enable_output",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_MENU_CURSOR,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={probatio.Required(ATTR_CURSOR): probatio.In(CURSOR_TYPE_MAP)},
        func="menu_cursor",
    )
