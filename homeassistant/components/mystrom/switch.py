"""Support for myStrom switches/plugs."""
from __future__ import annotations

import logging

from pymystrom.exceptions import MyStromConnectionError
from pymystrom.switch import MyStromSwitch as _MyStromSwitch
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DEFAULT_NAME = "myStrom Switch"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the myStrom switch/plug integration."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)

    try:
        plug = _MyStromSwitch(host)
        await plug.get_state()
    except MyStromConnectionError as err:
        _LOGGER.error("No route to myStrom plug: %s", host)
        raise PlatformNotReady() from err

    async_add_entities([MyStromSwitch(plug, name)])


class MyStromSwitch(SwitchEntity):
    """Representation of a myStrom switch/plug."""

    def __init__(self, plug, name):
        """Initialize the myStrom switch/plug."""
        self._name = name
        self.plug = plug
        self._available = True
        self.relay = None

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return bool(self.relay)

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self.plug._mac  # pylint: disable=protected-access

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._available

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        try:
            await self.plug.turn_on()
        except MyStromConnectionError:
            _LOGGER.error("No route to myStrom plug")

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        try:
            await self.plug.turn_off()
        except MyStromConnectionError:
            _LOGGER.error("No route to myStrom plug")

    async def async_update(self):
        """Get the latest data from the device and update the data."""
        try:
            await self.plug.get_state()
            self.relay = self.plug.relay
            self._available = True
        except MyStromConnectionError:
            if self._available:
                self._available = False
                _LOGGER.error("No route to myStrom plug")
