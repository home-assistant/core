"""
Connects to an ISY-994 controller and loads relevant components to control its
devices. Also contains the base classes for ISY Sensors, Lights, and Switches.
"""
# system imports
import logging
from urllib.parse import urlparse

# addon library imports
import PyISY

# homeassistant imports
from homeassistant import bootstrap
from homeassistant.loader import get_component
from homeassistant.helpers import validate_config
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import (
    CONF_HOST, CONF_USERNAME, CONF_PASSWORD, EVENT_PLATFORM_DISCOVERED,
    ATTR_SERVICE, ATTR_DISCOVERED, ATTR_FRIENDLY_NAME)

# homeassistant constants
DOMAIN = "isy994"
DEPENDENCIES = []
DISCOVER_LIGHTS = "isy994.lights"
DISCOVER_SWITCHES = "isy994.switches"
DISCOVER_SENSORS = "isy994.sensors"
ISY = None

# setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def setup(hass, config):
    # pull values from configuration file
    if not validate_config(config,
                           {DOMAIN: [CONF_HOST, CONF_USERNAME, CONF_PASSWORD]},
                           logger):
        return False
    else:
        user = config[DOMAIN][CONF_USERNAME]
        password = config[DOMAIN][CONF_PASSWORD]
        host = urlparse(config[DOMAIN][CONF_HOST])
        addr = host.geturl()
        if host.scheme == 'http':
            addr = addr.replace('http://', '')
            https = False
        elif host.scheme == 'https':
            addr = addr.replace('https://', '')
            https = True
        else:
            logger.error('isy994 host value in configuration ' +
                         'file is invalid.')
            return False
        port = host.port
        addr = addr.replace(':{}'.format(port), '')

    # connect to ISY controller
    global ISY
    ISY = PyISY.ISY(addr, port, user, password, use_https=https, log=logger)
    if not ISY.connected:
        return False

    # Load components for the devices in the ISY controller that we support
    for comp_name, discovery in ((('sensor', DISCOVER_SENSORS),
                                  ('light', DISCOVER_LIGHTS),
                                  ('switch', DISCOVER_SWITCHES))):
        component = get_component(comp_name)
        bootstrap.setup_component(hass, component.DOMAIN, config)
        hass.bus.fire(EVENT_PLATFORM_DISCOVERED,
                      {ATTR_SERVICE: discovery,
                       ATTR_DISCOVERED: {}})

    ISY.auto_update = True
    return True


class ISYDeviceABC(ToggleEntity):
    """ Abstract Class for an ISY device within home assistant. """

    _attrs = {}
    _onattrs = []
    _states = []
    _dtype = None
    _domain = None

    def __init__(self, node):
        # setup properties
        self.node = node

        # track changes
        self._changeHandler = self.node.status. \
            subscribe('changed', self.onUpdate)

    def __del__(self):
        """ cleanup subscriptions because it is the right thing to do. """
        self._changeHandler.unsubscribe()

    @property
    def domain(self):
        return self._domain

    @property
    def dtype(self):
        if self._dtype in ['analog', 'binary']:
            return self._dtype
        return 'binary' if self._units is None else 'analog'

    @property
    def should_poll(self):
        return False

    @property
    def value(self):
        """ returns the unclean value from the controller """
        return self.node.status._val

    @property
    def state_attributes(self):
        attr = {ATTR_FRIENDLY_NAME: self.name}
        for name, prop in self._attrs.items():
            attr[name] = getattr(self, prop)
        return attr

    @property
    def unique_id(self):
        """ Returns the id of this isy sensor """
        return self.node._id

    @property
    def name(self):
        """ Returns the name of the node if any. """
        return self.node.name

    def update(self):
        """ Update state of the sensor. """
        # ISY objects are automatically updated by the ISY's event stream
        pass

    def onUpdate(self, e):
        """ Handles the update received event. """
        self.update_ha_state()

    @property
    def is_on(self):
        return self.value > 0

    @property
    def is_open(self):
        return self.is_on

    @property
    def state(self):
        """ Returns the state of the node. """
        if len(self._states) > 0:
            return self._states[0] if self.is_on else self._states[1]
        return self.value

    def turn_on(self, **kwargs):
        """ turns the device on """
        if self.domain is not 'sensor':
            attrs = [kwargs.get(name) for name in self._onattrs]
            self.node.on(*attrs)
        else:
            logger.error('ISY cannot turn on sensors.')

    def turn_off(self, **kwargs):
        """ turns the device off """
        if self.domain is not 'sensor':
            self.node.off()
        else:
            logger.error('ISY cannot turn off sensors.')

    @property
    def unit_of_measurement(self):
        try:
            return self.node.units
        except AttributeError:
            return None
