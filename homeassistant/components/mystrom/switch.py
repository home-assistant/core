"""Support for myStrom switches/plugs."""
from __future__ import annotations

import logging
from typing import Any

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
        self.plug = plug
        self._attr_name = name
        self._attr_unique_id = self.plug.mac

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.plug.turn_on()
        except MyStromConnectionError:
            _LOGGER.error("No route to myStrom plug")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.plug.turn_off()
        except MyStromConnectionError:
            _LOGGER.error("No route to myStrom plug")

    async def async_update(self) -> None:
        """Get the latest data from the device and update the data."""
        try:
            await self.plug.get_state()
            self._attr_is_on = self.plug.relay
            self._attr_available = True
        except MyStromConnectionError:
            if self.available:
                self._attr_available = False
                _LOGGER.error("No route to myStrom plug")
