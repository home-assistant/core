"""YoLink services."""

from enum import StrEnum

import probatio
from yolink.client_request import ClientRequest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import ATTR_REPEAT, ATTR_TEXT_MESSAGE, ATTR_TONE, ATTR_VOLUME, DOMAIN


class YoLinkService(StrEnum):
    """Store keys for YoLink services."""

    PLAY_ON_SPEAKER_HUB = "play_on_speaker_hub"


class YoLinkServiceArgument(StrEnum):
    """Store keys for YoLink service arguments."""

    TARGET_DEVICE = "target_device"
    MESSAGE = "message"
    TONE = "tone"
    VOLUME = "volume"
    REPEAT = "repeat"


_SPEAKER_HUB_PLAY_CALL_OPTIONAL_ATTRS = (
    (ATTR_VOLUME, lambda x: x),
    (ATTR_TONE, lambda x: x.capitalize()),
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for YoLink integration."""

    async def handle_speaker_hub_play_call(service_call: ServiceCall) -> None:
        """Handle Speaker Hub audio play call."""
        service_data = service_call.data
        device, config_entry = dr.async_get_device_and_config_entry_for_domain(
            hass, service_data[YoLinkServiceArgument.TARGET_DEVICE], domain=DOMAIN
        )
        if device is not None:
            if (
                config_entry is None
                or config_entry.state is not ConfigEntryState.LOADED
            ):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_config_entry",
                )
            home_store = config_entry.runtime_data
            for identifier in device.identifiers:
                if (
                    device_coordinator := home_store.device_coordinators.get(
                        identifier[1]
                    )
                ) is not None:
                    params = {
                        ATTR_TEXT_MESSAGE: service_data[YoLinkServiceArgument.MESSAGE],
                        ATTR_REPEAT: service_data[YoLinkServiceArgument.REPEAT],
                    }

                    for attr, transform in _SPEAKER_HUB_PLAY_CALL_OPTIONAL_ATTRS:
                        if attr in service_data:
                            params[attr] = transform(service_data[attr])

                    play_request = ClientRequest("playAudio", params)
                    await device_coordinator.device.call_device(play_request)

    hass.services.async_register(
        domain=DOMAIN,
        service=YoLinkService.PLAY_ON_SPEAKER_HUB,
        schema=probatio.Schema(
            {
                probatio.Required(YoLinkServiceArgument.TARGET_DEVICE): cv.string,
                probatio.Optional(YoLinkServiceArgument.TONE): cv.string,
                probatio.Required(YoLinkServiceArgument.MESSAGE): cv.string,
                probatio.Optional(YoLinkServiceArgument.VOLUME): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=0, max=15)
                ),
                probatio.Optional(
                    YoLinkServiceArgument.REPEAT, default=0
                ): probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=10)),
            },
        ),
        service_func=handle_speaker_hub_play_call,
    )
