"""Support for Edimax switches."""

from __future__ import annotations

from typing import Any

from pyedimax.smartplug import SmartPlug
import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DOMAIN = "edimax"

DEFAULT_NAME = "Edimax Smart Plug"
DEFAULT_PASSWORD = "1234"
DEFAULT_USERNAME = "admin"

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Find and return Edimax Smart Plugs."""
    host = config.get(CONF_HOST)
    auth = (config.get(CONF_USERNAME), config.get(CONF_PASSWORD))
    name = config.get(CONF_NAME)

    add_entities([SmartPlugSwitch(SmartPlug(host, auth), name)], True)


class SmartPlugSwitch(SwitchEntity):
    """Representation an Edimax Smart Plug switch."""

    def __init__(self, smartplug, name):
        """Initialize the switch."""
        self.smartplug = smartplug
        self._attr_name = name
        self._attr_is_on = False
        self._info = None

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.smartplug.state = "ON"

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.smartplug.state = "OFF"

    def update(self) -> None:
        """Update edimax switch."""
        if not self._info:
            self._info = self.smartplug.info
            self._attr_unique_id = self._info["mac"]

        self._attr_is_on = self.smartplug.state == "ON"
