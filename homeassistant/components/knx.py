"""
Support for KNX components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/knx/
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP, CONF_HOST, CONF_PORT)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['knxip==0.3.3']

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = '3671'
DOMAIN = 'knx'

EVENT_KNX_FRAME_RECEIVED = 'knx_frame_received'

KNXTUNNEL = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup the connection to the KNX IP interface."""
    global KNXTUNNEL

    from knxip.ip import KNXIPTunnel
    from knxip.core import KNXException

    host = config[DOMAIN].get(CONF_HOST)
    port = config[DOMAIN].get(CONF_PORT)

    if host is '0.0.0.0':
        _LOGGER.debug("Will try to auto-detect KNX/IP gateway")

    KNXTUNNEL = KNXIPTunnel(host, port)
    try:
        res = KNXTUNNEL.connect()
        _LOGGER.debug("Res = %s", res)
        if not res:
            _LOGGER.exception("Could not connect to KNX/IP interface %s", host)
            return False

    except KNXException as ex:
        _LOGGER.exception("Can't connect to KNX/IP interface: %s", ex)
        KNXTUNNEL = None
        return False

    _LOGGER.info("KNX IP tunnel to %s:%i established", host, port)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, close_tunnel)
    return True


def close_tunnel(_data):
    """Close the NKX tunnel connection on shutdown."""
    global KNXTUNNEL

    KNXTUNNEL.disconnect()
    KNXTUNNEL = None


class KNXConfig(object):
    """Handle the fetching of configuration from the config file."""

    def __init__(self, config):
        """Initialize the configuration."""
        from knxip.core import parse_group_address

        self.config = config
        self.should_poll = config.get('poll', True)
        if config.get('address'):
            self._address = parse_group_address(config.get('address'))
        else:
            self._address = None
        if self.config.get('state_address'):
            self._state_address = parse_group_address(
                self.config.get('state_address'))
        else:
            self._state_address = None

    @property
    def name(self):
        """The name given to the entity."""
        return self.config['name']

    @property
    def address(self):
        """The address of the device as an integer value.

        3 types of addresses are supported:
        integer - 0-65535
        2 level - a/b
        3 level - a/b/c
        """
        return self._address

    @property
    def state_address(self):
        """The group address the device sends its current state to.

        Some KNX devices can send the current state to a seperate
        group address. This makes send e.g. when an actuator can
        be switched but also have a timer functionality.
        """
        return self._state_address


class KNXGroupAddress(Entity):
    """Representation of devices connected to a KNX group address."""

    def __init__(self, hass, config):
        """Initialize the device."""
        self._config = config
        self._state = False
        self._data = None
        _LOGGER.debug("Initalizing KNX group address %s", self.address)

        def handle_knx_message(addr, data):
            """Handle an incoming KNX frame.

            Handle an incoming frame and update our status if it contains
            information relating to this device.
            """
            if (addr == self.state_address) or (addr == self.address):
                self._state = data
                self.update_ha_state()

        KNXTUNNEL.register_listener(self.address, handle_knx_message)
        if self.state_address:
            KNXTUNNEL.register_listener(self.state_address, handle_knx_message)

    @property
    def name(self):
        """The entity's display name."""
        return self._config.name

    @property
    def config(self):
        """The entity's configuration."""
        return self._config

    @property
    def should_poll(self):
        """Return the state of the polling, if needed."""
        return self._config.should_poll

    @property
    def is_on(self):
        """Return True if the value is not 0 is on, else False."""
        if self.should_poll:
            self.update()
        return self._state != 0

    @property
    def address(self):
        """Return the KNX group address."""
        return self._config.address

    @property
    def state_address(self):
        """Return the KNX group address."""
        return self._config.state_address

    @property
    def cache(self):
        """The name given to the entity."""
        return self._config.config.get('cache', True)

    def group_write(self, value):
        """Write to the group address."""
        KNXTUNNEL.group_write(self.address, [value])

    def update(self):
        """Get the state from KNX bus or cache."""
        from knxip.core import KNXException

        try:
            if self.state_address:
                res = KNXTUNNEL.group_read(
                    self.state_address, use_cache=self.cache)
            else:
                res = KNXTUNNEL.group_read(self.address, use_cache=self.cache)

            if res:
                self._state = res[0]
                self._data = res
            else:
                _LOGGER.debug(
                    "Unable to read from KNX address: %s (None)", self.address)

        except KNXException:
            _LOGGER.exception(
                "Unable to read from KNX address: %s", self.address)
            return False


class KNXMultiAddressDevice(Entity):
    """Representation of devices connected to a multiple KNX group address.

    This is needed for devices like dimmers or shutter actuators as they have
    to be controlled by multiple group addresses.
    """

    names = {}
    values = {}

    def __init__(self, hass, config, required, optional=None):
        """Initialize the device.

        The namelist argument lists the required addresses. E.g. for a dimming
        actuators, the namelist might look like:
        onoff_address: 0/0/1
        brightness_address: 0/0/2
        """
        from knxip.core import parse_group_address, KNXException

        self._config = config
        self._state = False
        self._data = None
        _LOGGER.debug("Initalizing KNX multi address device")

        # parse required addresses
        for name in required:
            _LOGGER.info(name)
            paramname = '{}{}'.format(name, '_address')
            addr = self._config.config.get(paramname)
            if addr is None:
                _LOGGER.exception(
                    "Required KNX group address %s missing", paramname)
                raise KNXException(
                    "Group address for %s missing in configuration", paramname)
            addr = parse_group_address(addr)
            self.names[addr] = name

        # parse optional addresses
        for name in optional:
            paramname = '{}{}'.format(name, '_address')
            addr = self._config.config.get(paramname)
            if addr:
                try:
                    addr = parse_group_address(addr)
                except KNXException:
                    _LOGGER.exception("Cannot parse group address %s", addr)
                self.names[addr] = name

    @property
    def name(self):
        """The entity's display name."""
        return self._config.name

    @property
    def config(self):
        """The entity's configuration."""
        return self._config

    @property
    def should_poll(self):
        """Return the state of the polling, if needed."""
        return self._config.should_poll

    @property
    def cache(self):
        """The name given to the entity."""
        return self._config.config.get('cache', True)

    def has_attribute(self, name):
        """Check if the attribute with the given name is defined.

        This is mostly important for optional addresses.
        """
        for attributename, dummy_attribute in self.names.items():
            if attributename == name:
                return True
        return False

    def value(self, name):
        """Return the value to a given named attribute."""
        from knxip.core import KNXException

        addr = None
        for attributeaddress, attributename in self.names.items():
            if attributename == name:
                addr = attributeaddress

        if addr is None:
            _LOGGER.exception("Attribute %s undefined", name)
            return False

        try:
            res = KNXTUNNEL.group_read(addr, use_cache=self.cache)
        except KNXException:
            _LOGGER.exception("Unable to read from KNX address: %s", addr)
            return False

        return res

    def set_value(self, name, value):
        """Set the value of a given named attribute."""
        from knxip.core import KNXException

        addr = None
        for attributeaddress, attributename in self.names.items():
            if attributename == name:
                addr = attributeaddress

        if addr is None:
            _LOGGER.exception("Attribute %s undefined", name)
            return False

        try:
            KNXTUNNEL.group_write(addr, value)
        except KNXException:
            _LOGGER.exception("Unable to write to KNX address: %s", addr)
            return False

        return True
