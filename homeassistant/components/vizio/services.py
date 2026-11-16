"""Vizio SmartCast services."""

from enum import StrEnum

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN


class VizioService(StrEnum):
    """Store keys for Vizio services."""

    SEND_TEXT = "send_text"
    UPDATE_SETTING = "update_setting"


class VizioServiceArgument(StrEnum):
    """Store keys for Vizio service arguments."""

    TEXT = "text"
    SETTING_TYPE = "setting_type"
    SETTING_NAME = "setting_name"
    NEW_VALUE = "new_value"


UPDATE_SETTING_SCHEMA: VolDictType = {
    probatio.Required(VizioServiceArgument.SETTING_TYPE): probatio.All(
        cv.string, probatio.Lower, cv.slugify
    ),
    probatio.Required(VizioServiceArgument.SETTING_NAME): probatio.All(
        cv.string, probatio.Lower, cv.slugify
    ),
    probatio.Required(VizioServiceArgument.NEW_VALUE): probatio.Any(
        probatio.Coerce(int), cv.string
    ),
}

SEND_TEXT_SCHEMA: VolDictType = {
    probatio.Required(VizioServiceArgument.TEXT): cv.string,
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        VizioService.UPDATE_SETTING,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=UPDATE_SETTING_SCHEMA,
        func="async_update_setting",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        VizioService.SEND_TEXT,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=SEND_TEXT_SCHEMA,
        func="async_send_text",
    )
