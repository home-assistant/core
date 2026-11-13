"""Services for the TP-Link Smart Home integration."""

from enum import StrEnum

import probatio

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN


class TPLinkService(StrEnum):
    """Store keys for TP-Link Smart Home services."""

    SEQUENCE_EFFECT = "sequence_effect"
    RANDOM_EFFECT = "random_effect"


class TPLinkServiceArgument(StrEnum):
    """Store keys for TP-Link Smart Home service arguments."""

    SEQUENCE = "sequence"
    SEGMENTS = "segments"
    BRIGHTNESS = "brightness"
    DURATION = "duration"
    REPEAT_TIMES = "repeat_times"
    TRANSITION = "transition"
    SPREAD = "spread"
    DIRECTION = "direction"
    INIT_STATES = "init_states"
    BACKGROUNDS = "backgrounds"
    FADEOFF = "fadeoff"
    HUE_RANGE = "hue_range"
    SATURATION_RANGE = "saturation_range"
    BRIGHTNESS_RANGE = "brightness_range"
    TRANSITION_RANGE = "transition_range"
    RANDOM_SEED = "random_seed"


HUE = probatio.Range(min=0, max=360)
SAT = probatio.Range(min=0, max=100)
VAL = probatio.Range(min=0, max=100)
TRANSITION = probatio.Range(min=0, max=6000)
HSV_SEQUENCE = probatio.ExactSequence((HUE, SAT, VAL))

BASE_EFFECT_DICT: VolDictType = {
    probatio.Optional(TPLinkServiceArgument.BRIGHTNESS, default=100): probatio.All(
        probatio.Coerce(int), probatio.Percentage()
    ),
    probatio.Optional(TPLinkServiceArgument.DURATION, default=0): probatio.All(
        probatio.Coerce(int), probatio.Range(min=0, max=5000)
    ),
    probatio.Optional(TPLinkServiceArgument.TRANSITION, default=0): probatio.All(
        probatio.Coerce(int), TRANSITION
    ),
    probatio.Optional(TPLinkServiceArgument.SEGMENTS, default=[0]): probatio.All(
        cv.ensure_list_csv,
        probatio.Length(min=1, max=80),
        [probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=80))],
    ),
}

SEQUENCE_EFFECT_DICT: VolDictType = {
    **BASE_EFFECT_DICT,
    probatio.Required(TPLinkServiceArgument.SEQUENCE): probatio.All(
        probatio.EnsureList(),
        probatio.Length(min=1, max=16),
        [probatio.All(probatio.Coerce(tuple), HSV_SEQUENCE)],
    ),
    probatio.Optional(TPLinkServiceArgument.REPEAT_TIMES, default=0): probatio.All(
        probatio.Coerce(int), probatio.Range(min=0, max=10)
    ),
    probatio.Optional(TPLinkServiceArgument.SPREAD, default=1): probatio.All(
        probatio.Coerce(int), probatio.Range(min=1, max=16)
    ),
    probatio.Optional(TPLinkServiceArgument.DIRECTION, default=4): probatio.All(
        probatio.Coerce(int), probatio.Range(min=1, max=4)
    ),
}

RANDOM_EFFECT_DICT: VolDictType = {
    **BASE_EFFECT_DICT,
    probatio.Optional(TPLinkServiceArgument.FADEOFF, default=0): probatio.All(
        probatio.Coerce(int), probatio.Range(min=0, max=3000)
    ),
    probatio.Optional(TPLinkServiceArgument.HUE_RANGE): probatio.All(
        cv.ensure_list_csv, [probatio.Coerce(int)], probatio.ExactSequence((HUE, HUE))
    ),
    probatio.Optional(TPLinkServiceArgument.SATURATION_RANGE): probatio.All(
        cv.ensure_list_csv, [probatio.Coerce(int)], probatio.ExactSequence((SAT, SAT))
    ),
    probatio.Optional(TPLinkServiceArgument.BRIGHTNESS_RANGE): probatio.All(
        cv.ensure_list_csv, [probatio.Coerce(int)], probatio.ExactSequence((VAL, VAL))
    ),
    probatio.Optional(TPLinkServiceArgument.TRANSITION_RANGE): probatio.All(
        cv.ensure_list_csv,
        [probatio.Coerce(int)],
        probatio.ExactSequence((TRANSITION, TRANSITION)),
    ),
    probatio.Required(TPLinkServiceArgument.INIT_STATES): probatio.All(
        cv.ensure_list_csv, [probatio.Coerce(int)], HSV_SEQUENCE
    ),
    probatio.Optional(TPLinkServiceArgument.RANDOM_SEED, default=100): probatio.All(
        probatio.Coerce(int), probatio.Range(min=1, max=600)
    ),
    probatio.Optional(TPLinkServiceArgument.BACKGROUNDS): probatio.All(
        probatio.EnsureList(),
        probatio.Length(min=1, max=16),
        [probatio.All(probatio.Coerce(tuple), HSV_SEQUENCE)],
    ),
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the TP-Link Smart Home integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        TPLinkService.RANDOM_EFFECT,
        entity_domain=LIGHT_DOMAIN,
        schema=RANDOM_EFFECT_DICT,
        func="async_set_random_effect",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        TPLinkService.SEQUENCE_EFFECT,
        entity_domain=LIGHT_DOMAIN,
        schema=SEQUENCE_EFFECT_DICT,
        func="async_set_sequence_effect",
    )
