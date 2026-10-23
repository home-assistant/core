"""Services for the siren integration."""

from typing import TYPE_CHECKING, TypedDict, cast

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import VolDictType

from .const import (
    DATA_COMPONENT,
    DOMAIN,
    SirenEntityFeature,
    SirenService,
    SirenServiceArgument,
)

if TYPE_CHECKING:
    from .entity import SirenEntity

TURN_ON_SCHEMA: VolDictType = {
    probatio.Optional(SirenServiceArgument.TONE): probatio.Any(
        probatio.Coerce(int), cv.string
    ),
    probatio.Optional(SirenServiceArgument.DURATION): cv.positive_int,
    probatio.Optional(SirenServiceArgument.VOLUME_LEVEL): cv.small_float,
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
        params.pop(SirenServiceArgument.TONE.value, None)
    elif (tone := params.get(SirenServiceArgument.TONE.value)) is not None:
        # Raise an exception if the specified tone isn't available
        is_tone_dict_value = bool(
            isinstance(siren.available_tones, dict)
            and tone in siren.available_tones.values()
        )
        if not siren.available_tones or (
            tone not in siren.available_tones and not is_tone_dict_value
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_tone",
                translation_placeholders={
                    "entity_id": siren.entity_id,
                    "tone": str(tone),
                },
            )

        # If available tones is a dict, and the tone provided is a dict value, we need
        # to transform it to the corresponding dict key before returning
        if is_tone_dict_value:
            assert isinstance(siren.available_tones, dict)
            params[SirenServiceArgument.TONE.value] = next(
                key for key, value in siren.available_tones.items() if value == tone
            )

    if not siren.supported_features & SirenEntityFeature.DURATION:
        params.pop(SirenServiceArgument.DURATION.value, None)
    if not siren.supported_features & SirenEntityFeature.VOLUME_SET:
        params.pop(SirenServiceArgument.VOLUME_LEVEL.value, None)

    return params


async def _async_handle_turn_on_service(siren: SirenEntity, call: ServiceCall) -> None:
    """Handle turning a siren on."""
    data = {
        k: v
        for k, v in call.data.items()
        if k
        in (
            SirenServiceArgument.TONE,
            SirenServiceArgument.DURATION,
            SirenServiceArgument.VOLUME_LEVEL,
        )
    }
    await siren.async_turn_on(
        **process_turn_on_params(siren, cast(SirenTurnOnServiceParameters, data))
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the siren services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SirenService.TURN_ON,
        TURN_ON_SCHEMA,
        _async_handle_turn_on_service,
        [SirenEntityFeature.TURN_ON],
    )
    component.async_register_entity_service(
        SirenService.TURN_OFF, None, "async_turn_off", [SirenEntityFeature.TURN_OFF]
    )
    component.async_register_entity_service(
        SirenService.TOGGLE,
        None,
        "async_toggle",
        [SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF],
    )
