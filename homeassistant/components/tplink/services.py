"""Services for the TP-Link Smart Home integration."""

import probatio

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN

SERVICE_RANDOM_EFFECT = "random_effect"
SERVICE_SEQUENCE_EFFECT = "sequence_effect"

HUE = probatio.Range(min=0, max=360)
SAT = probatio.Range(min=0, max=100)
VAL = probatio.Range(min=0, max=100)
TRANSITION = probatio.Range(min=0, max=6000)
HSV_SEQUENCE = probatio.ExactSequence((HUE, SAT, VAL))

BASE_EFFECT_DICT: VolDictType = {
    probatio.Optional("brightness", default=100): probatio.All(
        probatio.Coerce(int), probatio.Percentage()
    ),
    probatio.Optional("duration", default=0): probatio.All(
        probatio.Coerce(int), probatio.Range(min=0, max=5000)
    ),
    probatio.Optional("transition", default=0): probatio.All(
        probatio.Coerce(int), TRANSITION
    ),
    probatio.Optional("segments", default=[0]): probatio.All(
        cv.ensure_list_csv,
        probatio.Length(min=1, max=80),
        [probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=80))],
    ),
}

SEQUENCE_EFFECT_DICT: VolDictType = {
    **BASE_EFFECT_DICT,
    probatio.Required("sequence"): probatio.All(
        probatio.EnsureList(),
        probatio.Length(min=1, max=16),
        [probatio.All(probatio.Coerce(tuple), HSV_SEQUENCE)],
    ),
    probatio.Optional("repeat_times", default=0): probatio.All(
        probatio.Coerce(int), probatio.Range(min=0, max=10)
    ),
    probatio.Optional("spread", default=1): probatio.All(
        probatio.Coerce(int), probatio.Range(min=1, max=16)
    ),
    probatio.Optional("direction", default=4): probatio.All(
        probatio.Coerce(int), probatio.Range(min=1, max=4)
    ),
}

RANDOM_EFFECT_DICT: VolDictType = {
    **BASE_EFFECT_DICT,
    probatio.Optional("fadeoff", default=0): probatio.All(
        probatio.Coerce(int), probatio.Range(min=0, max=3000)
    ),
    probatio.Optional("hue_range"): probatio.All(
        cv.ensure_list_csv, [probatio.Coerce(int)], probatio.ExactSequence((HUE, HUE))
    ),
    probatio.Optional("saturation_range"): probatio.All(
        cv.ensure_list_csv, [probatio.Coerce(int)], probatio.ExactSequence((SAT, SAT))
    ),
    probatio.Optional("brightness_range"): probatio.All(
        cv.ensure_list_csv, [probatio.Coerce(int)], probatio.ExactSequence((VAL, VAL))
    ),
    probatio.Optional("transition_range"): probatio.All(
        cv.ensure_list_csv,
        [probatio.Coerce(int)],
        probatio.ExactSequence((TRANSITION, TRANSITION)),
    ),
    probatio.Required("init_states"): probatio.All(
        cv.ensure_list_csv, [probatio.Coerce(int)], HSV_SEQUENCE
    ),
    probatio.Optional("random_seed", default=100): probatio.All(
        probatio.Coerce(int), probatio.Range(min=1, max=600)
    ),
    probatio.Optional("backgrounds"): probatio.All(
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
        SERVICE_RANDOM_EFFECT,
        entity_domain=LIGHT_DOMAIN,
        schema=RANDOM_EFFECT_DICT,
        func="async_set_random_effect",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SEQUENCE_EFFECT,
        entity_domain=LIGHT_DOMAIN,
        schema=SEQUENCE_EFFECT_DICT,
        func="async_set_sequence_effect",
    )
