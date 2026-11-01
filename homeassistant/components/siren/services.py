"""Services for the siren integration."""

from typing import TYPE_CHECKING, TypedDict, cast

import probatio

from homeassistant.const import SERVICE_TOGGLE, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import VolDictType

from .const import (
    ATTR_DURATION,
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    DATA_COMPONENT,
    SirenEntityFeature,
)

if TYPE_CHECKING:
    from . import SirenEntity

TURN_ON_SCHEMA: VolDictType = {
    probatio.Optional(ATTR_TONE): probatio.Any(probatio.Coerce(int), cv.string),
    probatio.Optional(ATTR_DURATION): cv.positive_int,
    probatio.Optional(ATTR_VOLUME_LEVEL): cv.small_float,
}


class SirenTurnOnServiceParameters(TypedDict, total=False):
    """Represent possible parameters to siren.turn_on service data dict type."""

    tone: int | str
    duration: int
    volume_level: float


def process_turn_on_params(
    siren: SirenEntity, params: SirenTurnOnServiceParameters
) -> SirenTurnOnServiceParameters:
    """Process turn_on service params.

    Filters out unsupported params and validates the rest.
    """

    if not siren.supported_features & SirenEntityFeature.TONES:
        params.pop(ATTR_TONE, None)
    elif (tone := params.get(ATTR_TONE)) is not None:
        # Raise an exception if the specified tone isn't available
        is_tone_dict_value = bool(
            isinstance(siren.available_tones, dict)
            and tone in siren.available_tones.values()
        )
        if not siren.available_tones or (
            tone not in siren.available_tones and not is_tone_dict_value
        ):
            raise ValueError(
                f"Invalid tone specified for entity {siren.entity_id}: {tone}, "
                "check the available_tones attribute for valid tones to pass in"
            )

        # If available tones is a dict, and the tone provided is a dict value, we need
        # to transform it to the corresponding dict key before returning
        if is_tone_dict_value:
            assert isinstance(siren.available_tones, dict)
            params[ATTR_TONE] = next(
                key for key, value in siren.available_tones.items() if value == tone
            )

    if not siren.supported_features & SirenEntityFeature.DURATION:
        params.pop(ATTR_DURATION, None)
    if not siren.supported_features & SirenEntityFeature.VOLUME_SET:
        params.pop(ATTR_VOLUME_LEVEL, None)

    return params


async def _async_handle_turn_on_service(siren: SirenEntity, call: ServiceCall) -> None:
    """Handle turning a siren on."""
    data = {
        k: v
        for k, v in call.data.items()
        if k in (ATTR_TONE, ATTR_DURATION, ATTR_VOLUME_LEVEL)
    }
    await siren.async_turn_on(
        **process_turn_on_params(siren, cast(SirenTurnOnServiceParameters, data))
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the siren services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SERVICE_TURN_ON,
        TURN_ON_SCHEMA,
        _async_handle_turn_on_service,
        [SirenEntityFeature.TURN_ON],
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF, None, "async_turn_off", [SirenEntityFeature.TURN_OFF]
    )
    component.async_register_entity_service(
        SERVICE_TOGGLE,
        None,
        "async_toggle",
        [SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF],
    )
