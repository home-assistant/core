"""Services for the Yamaha Network Receivers integration."""

from enum import StrEnum

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN
from .media_player import CURSOR_TYPE_MAP


class YamahaService(StrEnum):
    """Store keys for Yamaha services."""

    ENABLE_OUTPUT = "enable_output"
    MENU_CURSOR = "menu_cursor"
    SELECT_SCENE = "select_scene"


class YamahaServiceArgument(StrEnum):
    """Store keys for Yamaha service arguments."""

    PORT = "port"
    ENABLED = "enabled"
    CURSOR = "cursor"
    SCENE = "scene"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Yamaha Network Receivers integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        YamahaService.SELECT_SCENE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={probatio.Required(YamahaServiceArgument.SCENE): cv.string},
        func="set_scene",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        YamahaService.ENABLE_OUTPUT,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Required(YamahaServiceArgument.ENABLED): cv.boolean,
            probatio.Required(YamahaServiceArgument.PORT): cv.string,
        },
        func="enable_output",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        YamahaService.MENU_CURSOR,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Required(YamahaServiceArgument.CURSOR): probatio.In(
                CURSOR_TYPE_MAP
            )
        },
        func="menu_cursor",
    )
