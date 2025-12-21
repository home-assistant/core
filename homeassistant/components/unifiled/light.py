"""Support for Unifi Led lights."""

from __future__ import annotations

import logging
from typing import Any

from unifiled import unifiled
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=20443): vol.All(cv.port, cv.string),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Unifi LED platform."""

    # Assign configuration variables.
    # The configuration check takes care they are present.
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    api = unifiled(host, port, username=username, password=password)

    # Verify that passed in configuration works
    if not api.getloginstate():
        _LOGGER.error("Could not connect to unifiled controller")
        return

    add_entities(UnifiLedLight(light, api) for light in api.getlights())


class UnifiLedLight(LightEntity):
    """Representation of an unifiled Light."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, light: dict[str, Any], api: unifiled) -> None:
        """Init Unifi LED Light."""

        self._api = api
        self._light = light
        self._attr_name = light["name"]
        self._light_id = light["id"]
        self._attr_unique_id = light["id"]
        self._attr_is_on = light["status"]["output"]
        self._attr_available = light["isOnline"]
        self._attr_brightness = self._api.convertfrom100to255(light["status"]["led"])

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        self._api.setdevicebrightness(
            self._light_id,
            str(self._api.convertfrom255to100(kwargs.get(ATTR_BRIGHTNESS, 255))),
        )
        self._api.setdeviceoutput(self._light_id, 1)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        self._api.setdeviceoutput(self._light_id, 0)

    def update(self) -> None:
        """Update the light states."""
        self._attr_is_on = self._api.getlightstate(self._light_id)
        self._attr_brightness = self._api.convertfrom100to255(
            self._api.getlightbrightness(self._light_id)
        )
        self._attr_available = self._api.getlightavailable(self._light_id)
