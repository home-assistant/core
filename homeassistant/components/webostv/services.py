"""LG webOS TV services."""

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN, WebOsTvService, WebOsTvServiceArgument

BUTTON_SCHEMA: VolDictType = {
    probatio.Required(WebOsTvServiceArgument.BUTTON): cv.string
}
COMMAND_SCHEMA: VolDictType = {
    probatio.Required(WebOsTvServiceArgument.COMMAND): cv.string,
    probatio.Optional(WebOsTvServiceArgument.PAYLOAD): dict,
}
SOUND_OUTPUT_SCHEMA: VolDictType = {
    probatio.Required(WebOsTvServiceArgument.SOUND_OUTPUT): cv.string
}

SERVICES = (
    (
        WebOsTvService.BUTTON,
        BUTTON_SCHEMA,
        "async_button",
        SupportsResponse.NONE,
    ),
    (
        WebOsTvService.COMMAND,
        COMMAND_SCHEMA,
        "async_command",
        SupportsResponse.OPTIONAL,
    ),
    (
        WebOsTvService.SELECT_SOUND_OUTPUT,
        SOUND_OUTPUT_SCHEMA,
        "async_select_sound_output",
        SupportsResponse.OPTIONAL,
    ),
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    for service_name, schema, method, supports_response in SERVICES:
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            service_name,
            entity_domain=MEDIA_PLAYER_DOMAIN,
            schema=schema,
            func=method,
            supports_response=supports_response,
        )
