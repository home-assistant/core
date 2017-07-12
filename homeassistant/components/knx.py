"""
Support for KNX components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/knx/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP, CONF_HOST, CONF_PORT)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['knxip==0.4']

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 3671
DOMAIN = 'knx'

EVENT_KNX_FRAME_RECEIVED = 'knx_frame_received'
EVENT_KNX_FRAME_SEND = 'knx_frame_send'

KNXTUNNEL = None
CONF_LISTEN = "listen"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_LISTEN, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the connection to the KNX IP interface."""
    global KNXTUNNEL

    from knxip.ip import KNXIPTunnel
    from knxip.core import KNXException, parse_group_address

    host = config[DOMAIN].get(CONF_HOST)
    port = config[DOMAIN].get(CONF_PORT)

    if host == '0.0.0.0':
        _LOGGER.debug("Will try to auto-detect KNX/IP gateway")

    KNXTUNNEL = KNXIPTunnel(host, port)
    try:
        res = KNXTUNNEL.connect()
        _LOGGER.debug("Res = %s", res)
        if not res:
            _LOGGER.error("Could not connect to KNX/IP interface %s", host)
            return False

    except KNXException as ex:
        _LOGGER.exception("Can't connect to KNX/IP interface: %s", ex)
        KNXTUNNEL = None
        return False

    _LOGGER.info("KNX IP tunnel to %s:%i established", host, port)

    def received_knx_event(address, data):
        """Process received KNX message."""
        if len(data) == 1:
            data = data[0]
        hass.bus.fire('knx_event', {
            'address': address,
            'data': data
        })

    for listen in config[DOMAIN].get(CONF_LISTEN):
        _LOGGER.debug("Registering listener for %s", listen)
        try:
            KNXTUNNEL.register_listener(parse_group_address(listen),
                                        received_knx_event)
        except KNXException as knxexception:
            _LOGGER.error("Can't register KNX listener for address %s (%s)",
                          listen, knxexception)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, close_tunnel)

    # Listen to KNX events and send them to the bus
    def handle_knx_send(event):
        """Bridge knx_frame_send events to the KNX bus."""
        try:
            addr = event.data["address"]
        except KeyError:
            _LOGGER.error("KNX group address is missing")
            return

        try:
            data = event.data["data"]
        except KeyError:
            _LOGGER.error("KNX data block missing")
            return

        knxaddr = None
        try:
            addr = int(addr)
        except ValueError:
            pass

        if knxaddr is None:
            try:
                knxaddr = parse_group_address(addr)
            except KNXException:
                _LOGGER.error("KNX address format incorrect")
                return

        knxdata = None
        if isinstance(data, list):
            knxdata = data
        else:
            try:
                knxdata = [int(data) & 0xff]
            except ValueError:
                _LOGGER.error("KNX data format incorrect")
                return

        KNXTUNNEL.group_write(knxaddr, knxdata)

    # Listen for when knx_frame_send event is fired
    hass.bus.listen(EVENT_KNX_FRAME_SEND, handle_knx_send)

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
        """Return the name given to the entity."""
        return self.config['name']

    @property
    def address(self):
        """Return the address of the device as an integer value.

        3 types of addresses are supported:
        integer - 0-65535
        2 level - a/b
        3 level - a/b/c
        """
        return self._address

    @property
    def state_address(self):
        """Return the group address the device sends its current state to.

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
        _LOGGER.debug(
            "Initalizing KNX group address for %s (%s)",
            self.name, self.address
        )

        def handle_knx_message(addr, data):
            """Handle an incoming KNX frame.

            Handle an incoming frame and update our status if it contains
            information relating to this device.
            """
            if (addr == self.state_address) or (addr == self.address):
                self._state = data[0]
                self.schedule_update_ha_state()

        KNXTUNNEL.register_listener(self.address, handle_knx_message)
        if self.state_address:
            KNXTUNNEL.register_listener(self.state_address, handle_knx_message)

    @property
    def name(self):
        """Return the entity's display name."""
        return self._config.name

    @property
    def config(self):
        """Return the entity's configuration."""
        return self._config

    @property
    def should_poll(self):
        """Return the state of the polling, if needed."""
        return self._config.should_poll

    @property
    def is_on(self):
        """Return True if the value is not 0 is on, else False."""
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
        """Return the name given to the entity."""
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
                    "%s: unable to read from KNX address: %s (None)",
                    self.name, self.address
                )

        except KNXException:
            _LOGGER.exception(
                "%s: unable to read from KNX address: %s",
                self.name, self.address
            )
            return False


class KNXMultiAddressDevice(Entity):
    """Representation of devices connected to a multiple KNX group address.

    This is needed for devices like dimmers or shutter actuators as they have
    to be controlled by multiple group addresses.
    """

    def __init__(self, hass, config, required, optional=None):
        """Initialize the device.

        The namelist argument lists the required addresses. E.g. for a dimming
        actuators, the namelist might look like:
        onoff_address: 0/0/1
        brightness_address: 0/0/2
        """
        from knxip.core import parse_group_address, KNXException

        self.names = {}
        self.values = {}

        self._config = config
        self._state = False
        self._data = None
        _LOGGER.debug(
            "%s: initalizing KNX multi address device",
            self.name
        )

        settings = self._config.config
        if config.address:
            _LOGGER.debug(
                "%s: base address: address=%s",
                self.name, settings.get('address')
            )
            self.names[config.address] = 'base'
        if config.state_address:
            _LOGGER.debug(
                "%s, state address: state_address=%s",
                self.name, settings.get('state_address')
            )
            self.names[config.state_address] = 'state'

        # parse required addresses
        for name in required:
            paramname = '{}{}'.format(name, '_address')
            addr = settings.get(paramname)
            if addr is None:
                _LOGGER.error(
                    "%s: Required KNX group address %s missing",
                    self.name, paramname
                )
                raise KNXException(
                    "%s: Group address for {} missing in "
                    "configuration for {}".format(
                        self.name, paramname
                    )
                )
            _LOGGER.debug(
                "%s: (required parameter) %s=%s",
                self.name, paramname, addr
            )
            addr = parse_group_address(addr)
            self.names[addr] = name

        # parse optional addresses
        for name in optional:
            paramname = '{}{}'.format(name, '_address')
            addr = settings.get(paramname)
            _LOGGER.debug(
                "%s: (optional parameter) %s=%s",
                self.name, paramname, addr
            )
            if addr:
                try:
                    addr = parse_group_address(addr)
                except KNXException:
                    _LOGGER.exception(
                        "%s: cannot parse group address %s",
                        self.name, addr
                    )
                self.names[addr] = name

    @property
    def name(self):
        """Return the entity's display name."""
        return self._config.name

    @property
    def config(self):
        """Return the entity's configuration."""
        return self._config

    @property
    def should_poll(self):
        """Return the state of the polling, if needed."""
        return self._config.should_poll

    @property
    def cache(self):
        """Return the name given to the entity."""
        return self._config.config.get('cache', True)

    def has_attribute(self, name):
        """Check if the attribute with the given name is defined.

        This is mostly important for optional addresses.
        """
        for attributename in self.names.values():
            if attributename == name:
                return True
        return False

    def set_percentage(self, name, percentage):
        """Set a percentage in knx for a given attribute.

        DPT_Scaling / DPT 5.001 is a single byte scaled percentage
        """
        percentage = abs(percentage)  # only accept positive values
        scaled_value = percentage * 255 / 100
        value = min(255, scaled_value)
        return self.set_int_value(name, value)

    def get_percentage(self, name):
        """Get a percentage from knx for a given attribute.

        DPT_Scaling / DPT 5.001 is a single byte scaled percentage
        """
        value = self.get_int_value(name)
        percentage = round(value * 100 / 255)
        return percentage

    def set_int_value(self, name, value, num_bytes=1):
        """Set an integer value for a given attribute."""
        # KNX packets are big endian
        value = round(value)      # only accept integers
        b_value = value.to_bytes(num_bytes, byteorder='big')
        return self.set_value(name, list(b_value))

    def get_int_value(self, name):
        """Get an integer value for a given attribute."""
        # KNX packets are big endian
        summed_value = 0
        raw_value = self.value(name)
        try:
            # convert raw value in bytes
            for val in raw_value:
                summed_value *= 256
                summed_value += val
        except TypeError:
            # pknx returns a non-iterable type for unsuccessful reads
            pass

        return summed_value

    def value(self, name):
        """Return the value to a given named attribute."""
        from knxip.core import KNXException

        addr = None
        for attributeaddress, attributename in self.names.items():
            if attributename == name:
                addr = attributeaddress

        if addr is None:
            _LOGGER.error("%s: attribute '%s' undefined",
                          self.name, name)
            _LOGGER.debug(
                "%s: defined attributes: %s",
                self.name, str(self.names)
            )
            return False

        try:
            res = KNXTUNNEL.group_read(addr, use_cache=self.cache)
        except KNXException:
            _LOGGER.exception(
                "%s: unable to read from KNX address: %s",
                self.name, addr
            )
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
            _LOGGER.error("%s: attribute '%s' undefined",
                          self.name, name)
            _LOGGER.debug(
                "%s: defined attributes: %s",
                self.name, str(self.names)
            )
            return False

        try:
            KNXTUNNEL.group_write(addr, value)
        except KNXException:
            _LOGGER.exception(
                "%s: unable to write to KNX address: %s",
                self.name, addr
            )
            return False

        return True
