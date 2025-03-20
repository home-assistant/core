"""YoLink services."""

import voluptuous as vol
from yolink.client_request import ClientRequest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import (
    ATTR_REPEAT,
    ATTR_TARGET_DEVICE,
    ATTR_TEXT_MESSAGE,
    ATTR_TONE,
    ATTR_VOLUME,
    DOMAIN,
)

SERVICE_PLAY_ON_SPEAKER_HUB = "play_on_speaker_hub"

_SPEAKER_HUB_PLAY_CALL_OPTIONAL_ATTRS = (
    (ATTR_VOLUME, lambda x: x),
    (ATTR_TONE, lambda x: x.capitalize()),
)


def async_register_services(hass: HomeAssistant) -> None:
    """Register services for YoLink integration."""

    async def handle_speaker_hub_play_call(service_call: ServiceCall) -> None:
        """Handle Speaker Hub audio play call."""
        service_data = service_call.data
        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get(service_data[ATTR_TARGET_DEVICE])
        if device_entry is not None:
            for entry_id in device_entry.config_entries:
                if (entry := hass.config_entries.async_get_entry(entry_id)) is None:
                    continue
                if entry.domain == DOMAIN:
                    break
            if entry is None or entry.state != ConfigEntryState.LOADED:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_config_entry",
                )
            home_store = hass.data[DOMAIN][entry.entry_id]
            for identifier in device_entry.identifiers:
                if (
                    device_coordinator := home_store.device_coordinators.get(
                        identifier[1]
                    )
                ) is not None:
                    params = {
                        ATTR_TEXT_MESSAGE: service_data[ATTR_TEXT_MESSAGE],
                        ATTR_REPEAT: service_data[ATTR_REPEAT],
                    }

                    for attr, transform in _SPEAKER_HUB_PLAY_CALL_OPTIONAL_ATTRS:
                        if attr in service_data:
                            params[attr] = transform(service_data[attr])

                    play_request = ClientRequest("playAudio", params)
                    await device_coordinator.device.call_device(play_request)

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_PLAY_ON_SPEAKER_HUB,
        schema=vol.Schema(
            {
                vol.Required(ATTR_TARGET_DEVICE): cv.string,
                vol.Optional(ATTR_TONE): cv.string,
                vol.Required(ATTR_TEXT_MESSAGE): cv.string,
                vol.Optional(ATTR_VOLUME): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=15)
                ),
                vol.Optional(ATTR_REPEAT, default=0): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=10)
                ),
            },
        ),
        service_func=handle_speaker_hub_play_call,
    )
