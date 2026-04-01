"""Vizio SmartCast services."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN

SERVICE_UPDATE_SETTING = "update_setting"

ATTR_SETTING_TYPE = "setting_type"
ATTR_SETTING_NAME = "setting_name"
ATTR_NEW_VALUE = "new_value"

UPDATE_SETTING_SCHEMA: VolDictType = {
    vol.Required(ATTR_SETTING_TYPE): vol.All(cv.string, vol.Lower, cv.slugify),
    vol.Required(ATTR_SETTING_NAME): vol.All(cv.string, vol.Lower, cv.slugify),
    vol.Required(ATTR_NEW_VALUE): vol.Any(vol.Coerce(int), cv.string),
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_UPDATE_SETTING,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=UPDATE_SETTING_SCHEMA,
        func="async_update_setting",
    )
