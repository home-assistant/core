"""Support for Edimax switches."""
from __future__ import annotations

from pyedimax.smartplug import SmartPlug
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DOMAIN = "edimax"

DEFAULT_NAME = "Edimax Smart Plug"
DEFAULT_PASSWORD = "1234"
DEFAULT_USERNAME = "admin"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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
        self._name = name
        self._state = False
        self._info = None
        self._mac = None

    @property
    def unique_id(self):
        """Return the device's MAC address."""
        return self._mac

    @property
    def name(self):
        """Return the name of the Smart Plug, if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.smartplug.state = "ON"

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self.smartplug.state = "OFF"

    def update(self):
        """Update edimax switch."""
        if not self._info:
            self._info = self.smartplug.info
            self._mac = self._info["mac"]

        self._state = self.smartplug.state == "ON"
