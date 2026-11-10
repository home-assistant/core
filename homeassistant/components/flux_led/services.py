"""Services for the Magic Home integration."""

from enum import StrEnum

from flux_led.const import MultiColorEffects
import probatio

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN, TRANSITION_GRADUAL, TRANSITION_JUMP, TRANSITION_STROBE


class FluxLedService(StrEnum):
    """Store keys for Magic Home services."""

    SET_CUSTOM_EFFECT = "set_custom_effect"
    SET_ZONES = "set_zones"
    SET_MUSIC_MODE = "set_music_mode"


class FluxLedServiceArgument(StrEnum):
    """Store keys for Magic Home service arguments."""

    COLORS = "colors"
    SPEED_PCT = "speed_pct"
    TRANSITION = "transition"
    EFFECT = "effect"
    SENSITIVITY = "sensitivity"
    BRIGHTNESS = "brightness"
    LIGHT_SCREEN = "light_screen"
    FOREGROUND_COLOR = "foreground_color"
    BACKGROUND_COLOR = "background_color"


CUSTOM_EFFECT_DICT: VolDictType = {
    probatio.Required(FluxLedServiceArgument.COLORS): probatio.All(
        probatio.EnsureList(),
        probatio.Length(min=1, max=16),
        [
            probatio.All(
                probatio.Coerce(tuple),
                probatio.ExactSequence((cv.byte, cv.byte, cv.byte)),
            )
        ],
    ),
    probatio.Optional(FluxLedServiceArgument.SPEED_PCT, default=50): probatio.All(
        probatio.Coerce(int), probatio.Percentage()
    ),
    probatio.Optional(
        FluxLedServiceArgument.TRANSITION, default=TRANSITION_GRADUAL
    ): probatio.All(
        cv.string, probatio.In([TRANSITION_GRADUAL, TRANSITION_JUMP, TRANSITION_STROBE])
    ),
}
SET_MUSIC_MODE_DICT: VolDictType = {
    probatio.Optional(FluxLedServiceArgument.SENSITIVITY, default=100): probatio.All(
        probatio.Coerce(int), probatio.Percentage()
    ),
    probatio.Optional(FluxLedServiceArgument.BRIGHTNESS, default=100): probatio.All(
        probatio.Coerce(int), probatio.Percentage()
    ),
    probatio.Optional(FluxLedServiceArgument.EFFECT, default=1): probatio.All(
        probatio.Coerce(int), probatio.Range(min=0, max=16)
    ),
    probatio.Optional(FluxLedServiceArgument.LIGHT_SCREEN, default=False): bool,
    probatio.Optional(FluxLedServiceArgument.FOREGROUND_COLOR): probatio.All(
        probatio.Coerce(tuple), probatio.ExactSequence((cv.byte,) * 3)
    ),
    probatio.Optional(FluxLedServiceArgument.BACKGROUND_COLOR): probatio.All(
        probatio.Coerce(tuple), probatio.ExactSequence((cv.byte,) * 3)
    ),
}
SET_ZONES_DICT: VolDictType = {
    probatio.Required(FluxLedServiceArgument.COLORS): probatio.All(
        probatio.EnsureList(),
        probatio.Length(min=1, max=2048),
        [
            probatio.All(
                probatio.Coerce(tuple),
                probatio.ExactSequence((cv.byte, cv.byte, cv.byte)),
            )
        ],
    ),
    probatio.Optional(FluxLedServiceArgument.SPEED_PCT, default=50): probatio.All(
        probatio.Coerce(int), probatio.Percentage()
    ),
    probatio.Optional(
        FluxLedServiceArgument.EFFECT, default=MultiColorEffects.STATIC.name.lower()
    ): probatio.All(
        cv.string, probatio.In([effect.name.lower() for effect in MultiColorEffects])
    ),
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Magic Home integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        FluxLedService.SET_CUSTOM_EFFECT,
        entity_domain=LIGHT_DOMAIN,
        schema=CUSTOM_EFFECT_DICT,
        func="async_set_custom_effect",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        FluxLedService.SET_ZONES,
        entity_domain=LIGHT_DOMAIN,
        schema=SET_ZONES_DICT,
        func="async_set_zones",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        FluxLedService.SET_MUSIC_MODE,
        entity_domain=LIGHT_DOMAIN,
        schema=SET_MUSIC_MODE_DICT,
        func="async_set_music_mode",
    )
