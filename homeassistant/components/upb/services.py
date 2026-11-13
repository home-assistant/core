"""Services for the Universal Powerline Bus (UPB) integration."""

from enum import StrEnum

import probatio

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN


class UpbService(StrEnum):
    """Store keys for UPB services."""

    LIGHT_FADE_START = "light_fade_start"
    LIGHT_FADE_STOP = "light_fade_stop"
    LIGHT_BLINK = "light_blink"
    LINK_DEACTIVATE = "link_deactivate"
    LINK_GOTO = "link_goto"
    LINK_FADE_START = "link_fade_start"
    LINK_FADE_STOP = "link_fade_stop"
    LINK_BLINK = "link_blink"


class UpbServiceArgument(StrEnum):
    """Store keys for UPB service arguments."""

    BRIGHTNESS = "brightness"
    BRIGHTNESS_PCT = "brightness_pct"
    RATE = "rate"
    BLINK_RATE = "blink_rate"


VALID_BRIGHTNESS = probatio.All(probatio.Coerce(int), probatio.Clamp(min=0, max=255))
VALID_BRIGHTNESS_PCT = probatio.All(probatio.Coerce(float), probatio.Percentage())
VALID_RATE = probatio.All(probatio.Coerce(float), probatio.Clamp(min=-1, max=3600))

UPB_BRIGHTNESS_RATE_SCHEMA = probatio.All(
    probatio.AtLeastOne(
        UpbServiceArgument.BRIGHTNESS, UpbServiceArgument.BRIGHTNESS_PCT
    ),
    cv.make_entity_service_schema(
        {
            probatio.Exclusive(
                UpbServiceArgument.BRIGHTNESS, UpbServiceArgument.BRIGHTNESS
            ): VALID_BRIGHTNESS,
            probatio.Exclusive(
                UpbServiceArgument.BRIGHTNESS_PCT, UpbServiceArgument.BRIGHTNESS
            ): VALID_BRIGHTNESS_PCT,
            probatio.Optional(UpbServiceArgument.RATE, default=-1): VALID_RATE,
        }
    ),
)

UPB_BLINK_RATE_SCHEMA: VolDictType = {
    probatio.Required(UpbServiceArgument.BLINK_RATE, default=0.5): probatio.All(
        probatio.Coerce(float), probatio.Range(min=0, max=4.25)
    )
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Universal Powerline Bus (UPB) integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        UpbService.LIGHT_FADE_START,
        entity_domain=LIGHT_DOMAIN,
        schema=UPB_BRIGHTNESS_RATE_SCHEMA,
        func="async_light_fade_start",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        UpbService.LIGHT_FADE_STOP,
        entity_domain=LIGHT_DOMAIN,
        schema=None,
        func="async_light_fade_stop",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        UpbService.LIGHT_BLINK,
        entity_domain=LIGHT_DOMAIN,
        schema=UPB_BLINK_RATE_SCHEMA,
        func="async_light_blink",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        UpbService.LINK_DEACTIVATE,
        entity_domain=SCENE_DOMAIN,
        schema=None,
        func="async_link_deactivate",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        UpbService.LINK_FADE_STOP,
        entity_domain=SCENE_DOMAIN,
        schema=None,
        func="async_link_fade_stop",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        UpbService.LINK_GOTO,
        entity_domain=SCENE_DOMAIN,
        schema=UPB_BRIGHTNESS_RATE_SCHEMA,
        func="async_link_goto",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        UpbService.LINK_FADE_START,
        entity_domain=SCENE_DOMAIN,
        schema=UPB_BRIGHTNESS_RATE_SCHEMA,
        func="async_link_fade_start",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        UpbService.LINK_BLINK,
        entity_domain=SCENE_DOMAIN,
        schema=UPB_BLINK_RATE_SCHEMA,
        func="async_link_blink",
    )
