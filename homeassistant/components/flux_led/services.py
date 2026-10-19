"""Services for the Magic Home integration."""

from typing import Final

from flux_led.const import MultiColorEffects
import probatio

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import CONF_EFFECT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import (
    CONF_COLORS,
    CONF_SPEED_PCT,
    CONF_TRANSITION,
    DOMAIN,
    TRANSITION_GRADUAL,
    TRANSITION_JUMP,
    TRANSITION_STROBE,
)

ATTR_FOREGROUND_COLOR: Final = "foreground_color"
ATTR_BACKGROUND_COLOR: Final = "background_color"
ATTR_SENSITIVITY: Final = "sensitivity"
ATTR_LIGHT_SCREEN: Final = "light_screen"
SERVICE_CUSTOM_EFFECT: Final = "set_custom_effect"
SERVICE_SET_ZONES: Final = "set_zones"
SERVICE_SET_MUSIC_MODE: Final = "set_music_mode"
CUSTOM_EFFECT_DICT: VolDictType = {
    probatio.Required(CONF_COLORS): probatio.All(
        probatio.EnsureList(),
        probatio.Length(min=1, max=16),
        [
            probatio.All(
                probatio.Coerce(tuple),
                probatio.ExactSequence((cv.byte, cv.byte, cv.byte)),
            )
        ],
    ),
    probatio.Optional(CONF_SPEED_PCT, default=50): probatio.All(
        probatio.Coerce(int), probatio.Percentage()
    ),
    probatio.Optional(CONF_TRANSITION, default=TRANSITION_GRADUAL): probatio.All(
        cv.string, probatio.In([TRANSITION_GRADUAL, TRANSITION_JUMP, TRANSITION_STROBE])
    ),
}
SET_MUSIC_MODE_DICT: VolDictType = {
    probatio.Optional(ATTR_SENSITIVITY, default=100): probatio.All(
        probatio.Coerce(int), probatio.Percentage()
    ),
    probatio.Optional(ATTR_BRIGHTNESS, default=100): probatio.All(
        probatio.Coerce(int), probatio.Percentage()
    ),
    probatio.Optional(ATTR_EFFECT, default=1): probatio.All(
        probatio.Coerce(int), probatio.Range(min=0, max=16)
    ),
    probatio.Optional(ATTR_LIGHT_SCREEN, default=False): bool,
    probatio.Optional(ATTR_FOREGROUND_COLOR): probatio.All(
        probatio.Coerce(tuple), probatio.ExactSequence((cv.byte,) * 3)
    ),
    probatio.Optional(ATTR_BACKGROUND_COLOR): probatio.All(
        probatio.Coerce(tuple), probatio.ExactSequence((cv.byte,) * 3)
    ),
}
SET_ZONES_DICT: VolDictType = {
    probatio.Required(CONF_COLORS): probatio.All(
        probatio.EnsureList(),
        probatio.Length(min=1, max=2048),
        [
            probatio.All(
                probatio.Coerce(tuple),
                probatio.ExactSequence((cv.byte, cv.byte, cv.byte)),
            )
        ],
    ),
    probatio.Optional(CONF_SPEED_PCT, default=50): probatio.All(
        probatio.Coerce(int), probatio.Percentage()
    ),
    probatio.Optional(
        CONF_EFFECT, default=MultiColorEffects.STATIC.name.lower()
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
        SERVICE_CUSTOM_EFFECT,
        entity_domain=LIGHT_DOMAIN,
        schema=CUSTOM_EFFECT_DICT,
        func="async_set_custom_effect",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_ZONES,
        entity_domain=LIGHT_DOMAIN,
        schema=SET_ZONES_DICT,
        func="async_set_zones",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_MUSIC_MODE,
        entity_domain=LIGHT_DOMAIN,
        schema=SET_MUSIC_MODE_DICT,
        func="async_set_music_mode",
    )
