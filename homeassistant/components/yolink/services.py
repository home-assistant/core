"""YoLink services."""
import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import ATTR_REPEAT, ATTR_TEXT_MESSAGE, ATTR_TONE, ATTR_VOLUME, DOMAIN

SERVICE_PLAY_ON_SPEAKER_HUB = "play_on_speaker_hub"

_LOGGER = logging.getLogger(__name__)


def async_register_services(hass: HomeAssistant) -> None:
    """Register services for YoLink integration."""

    async def handle_speaker_hub_play_call(service_call: ServiceCall) -> None:
        """Handle Speaker Hub audio play call."""
        if service_call.service == SERVICE_PLAY_ON_SPEAKER_HUB:
            service_data = service_call.data
            _LOGGER.info(service_data)

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_PLAY_ON_SPEAKER_HUB,
        schema=vol.Schema(
            {
                vol.Required(ATTR_TONE): cv.string,
                vol.Required(ATTR_TEXT_MESSAGE): cv.string,
                vol.Required(ATTR_VOLUME): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=15)
                ),
                vol.Optional(ATTR_REPEAT, default=0): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=10)
                ),
            },
        ),
        service_func=handle_speaker_hub_play_call,
    )
