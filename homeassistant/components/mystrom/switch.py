"""Support for myStrom switches/plugs."""
import logging

from pymystrom.exceptions import MyStromConnectionError
from pymystrom.switch import MyStromSwitch as _MyStromSwitch
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

DEFAULT_NAME = "myStrom Switch"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the myStrom switch/plug integration."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)

    try:
        plug = _MyStromSwitch(host)
        await plug.get_state()
    except MyStromConnectionError:
        _LOGGER.error("No route to myStrom plug: %s", host)
        raise PlatformNotReady()

    async_add_entities([MyStromSwitch(plug, name, plug.mac)])


class MyStromSwitch(SwitchDevice):
    """Representation of a myStrom switch/plug."""

    def __init__(self, plug, name, mac):
        """Initialize the myStrom switch/plug."""
        self._name = name
        self.data = {}
        self.plug = plug
        self._available = True
        self.mac = mac
        self.firmware = None
        self.consumption = None
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
        return self.mac

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self._name,
            "manufacturer": DOMAIN,
            "model": "plug",
            "sw_version": self.firmware,
        }

    @property
    def current_power_w(self):
        """Return the current power consumption in W."""
        return self.consumption

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
            self.firmware = self.plug.firmware
            self.consumption = self.plug.consumption
            self.relay = self.plug.relay

            self._available = True
        except MyStromConnectionError:
            self.data = {"power": 0, "relay": False}
            self._available = False
            _LOGGER.error("No route to myStrom plug")
