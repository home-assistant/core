"""Services for the Universal Powerline Bus (UPB) integration."""

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN, UPB_BLINK_RATE_SCHEMA, UPB_BRIGHTNESS_RATE_SCHEMA

SERVICE_LIGHT_FADE_START = "light_fade_start"
SERVICE_LIGHT_FADE_STOP = "light_fade_stop"
SERVICE_LIGHT_BLINK = "light_blink"
SERVICE_LINK_DEACTIVATE = "link_deactivate"
SERVICE_LINK_FADE_STOP = "link_fade_stop"
SERVICE_LINK_GOTO = "link_goto"
SERVICE_LINK_FADE_START = "link_fade_start"
SERVICE_LINK_BLINK = "link_blink"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Universal Powerline Bus (UPB) integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_LIGHT_FADE_START,
        entity_domain=LIGHT_DOMAIN,
        schema=UPB_BRIGHTNESS_RATE_SCHEMA,
        func="async_light_fade_start",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_LIGHT_FADE_STOP,
        entity_domain=LIGHT_DOMAIN,
        schema=None,
        func="async_light_fade_stop",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_LIGHT_BLINK,
        entity_domain=LIGHT_DOMAIN,
        schema=UPB_BLINK_RATE_SCHEMA,
        func="async_light_blink",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_LINK_DEACTIVATE,
        entity_domain=SCENE_DOMAIN,
        schema=None,
        func="async_link_deactivate",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_LINK_FADE_STOP,
        entity_domain=SCENE_DOMAIN,
        schema=None,
        func="async_link_fade_stop",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_LINK_GOTO,
        entity_domain=SCENE_DOMAIN,
        schema=UPB_BRIGHTNESS_RATE_SCHEMA,
        func="async_link_goto",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_LINK_FADE_START,
        entity_domain=SCENE_DOMAIN,
        schema=UPB_BRIGHTNESS_RATE_SCHEMA,
        func="async_link_fade_start",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_LINK_BLINK,
        entity_domain=SCENE_DOMAIN,
        schema=UPB_BLINK_RATE_SCHEMA,
        func="async_link_blink",
    )
