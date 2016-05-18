"""
Connect to a MySensors gateway via pymysensors API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mysensors/
"""
import logging
import socket

import homeassistant.bootstrap as bootstrap
from homeassistant.const import (ATTR_BATTERY_LEVEL, ATTR_DISCOVERED,
                                 ATTR_SERVICE, CONF_OPTIMISTIC,
                                 EVENT_HOMEASSISTANT_START,
                                 EVENT_HOMEASSISTANT_STOP,
                                 EVENT_PLATFORM_DISCOVERED, STATE_OFF,
                                 STATE_ON, TEMP_CELSIUS)
from homeassistant.helpers import validate_config

CONF_GATEWAYS = 'gateways'
CONF_DEVICE = 'device'
CONF_DEBUG = 'debug'
CONF_PERSISTENCE = 'persistence'
CONF_PERSISTENCE_FILE = 'persistence_file'
CONF_VERSION = 'version'
CONF_BAUD_RATE = 'baud_rate'
CONF_TCP_PORT = 'tcp_port'
DEFAULT_VERSION = '1.4'
DEFAULT_BAUD_RATE = 115200
DEFAULT_TCP_PORT = 5003

DOMAIN = 'mysensors'
DEPENDENCIES = []
REQUIREMENTS = [
    'https://github.com/theolind/pymysensors/archive/'
    'cc5d0b325e13c2b623fa934f69eea7cd4555f110.zip#pymysensors==0.6']
_LOGGER = logging.getLogger(__name__)
ATTR_NODE_ID = 'node_id'
ATTR_CHILD_ID = 'child_id'
ATTR_DEVICE = 'device'

GATEWAYS = None

DISCOVER_SENSORS = 'mysensors.sensors'
DISCOVER_SWITCHES = 'mysensors.switches'
DISCOVER_LIGHTS = 'mysensors.lights'
DISCOVER_BINARY_SENSORS = 'mysensors.binary_sensor'

# Maps discovered services to their platforms
DISCOVERY_COMPONENTS = [
    ('sensor', DISCOVER_SENSORS),
    ('switch', DISCOVER_SWITCHES),
    ('light', DISCOVER_LIGHTS),
    ('binary_sensor', DISCOVER_BINARY_SENSORS),
]


def setup(hass, config):  # pylint: disable=too-many-locals
    """Setup the MySensors component."""
    if not validate_config(config,
                           {DOMAIN: [CONF_GATEWAYS]},
                           _LOGGER):
        return False
    if not all(CONF_DEVICE in gateway
               for gateway in config[DOMAIN][CONF_GATEWAYS]):
        _LOGGER.error('Missing required configuration items '
                      'in %s: %s', DOMAIN, CONF_DEVICE)
        return False

    import mysensors.mysensors as mysensors

    version = str(config[DOMAIN].get(CONF_VERSION, DEFAULT_VERSION))
    is_metric = (hass.config.temperature_unit == TEMP_CELSIUS)
    persistence = config[DOMAIN].get(CONF_PERSISTENCE, True)

    def setup_gateway(device, persistence_file, baud_rate, tcp_port):
        """Return gateway after setup of the gateway."""
        try:
            socket.inet_aton(device)
            # valid ip address
            gateway = mysensors.TCPGateway(
                device, event_callback=None, persistence=persistence,
                persistence_file=persistence_file, protocol_version=version,
                port=tcp_port)
        except OSError:
            # invalid ip address
            gateway = mysensors.SerialGateway(
                device, event_callback=None, persistence=persistence,
                persistence_file=persistence_file, protocol_version=version,
                baud=baud_rate)
        gateway.metric = is_metric
        gateway.debug = config[DOMAIN].get(CONF_DEBUG, False)
        optimistic = config[DOMAIN].get(CONF_OPTIMISTIC, False)
        gateway = GatewayWrapper(gateway, version, optimistic)
        # pylint: disable=attribute-defined-outside-init
        gateway.event_callback = gateway.callback_factory()

        def gw_start(event):
            """Callback to trigger start of gateway and any persistence."""
            gateway.start()
            hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                                 lambda event: gateway.stop())
            if persistence:
                for node_id in gateway.sensors:
                    gateway.event_callback('persistence', node_id)

        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, gw_start)

        return gateway

    # Setup all devices from config
    global GATEWAYS
    GATEWAYS = {}
    conf_gateways = config[DOMAIN][CONF_GATEWAYS]
    if isinstance(conf_gateways, dict):
        conf_gateways = [conf_gateways]

    for index, gway in enumerate(conf_gateways):
        device = gway[CONF_DEVICE]
        persistence_file = gway.get(
            CONF_PERSISTENCE_FILE,
            hass.config.path('mysensors{}.pickle'.format(index + 1)))
        baud_rate = gway.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE)
        tcp_port = gway.get(CONF_TCP_PORT, DEFAULT_TCP_PORT)
        GATEWAYS[device] = setup_gateway(
            device, persistence_file, baud_rate, tcp_port)

    for (component, discovery_service) in DISCOVERY_COMPONENTS:
        # Ensure component is loaded
        if not bootstrap.setup_component(hass, component, config):
            return False
        # Fire discovery event
        hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
            ATTR_SERVICE: discovery_service,
            ATTR_DISCOVERED: {}})

    return True


def pf_callback_factory(map_sv_types, devices, add_devices, entity_class):
    """Return a new callback for the platform."""
    def mysensors_callback(gateway, node_id):
        """Callback for mysensors platform."""
        if gateway.sensors[node_id].sketch_name is None:
            _LOGGER.info('No sketch_name: node %s', node_id)
            return

        for child in gateway.sensors[node_id].children.values():
            for value_type in child.values.keys():
                key = node_id, child.id, value_type
                if child.type not in map_sv_types or \
                        value_type not in map_sv_types[child.type]:
                    continue
                if key in devices:
                    devices[key].update_ha_state(True)
                    continue
                name = '{} {} {}'.format(
                    gateway.sensors[node_id].sketch_name, node_id, child.id)
                if isinstance(entity_class, dict):
                    device_class = entity_class[child.type]
                else:
                    device_class = entity_class
                devices[key] = device_class(
                    gateway, node_id, child.id, name, value_type, child.type)

                _LOGGER.info('Adding new devices: %s', devices[key])
                add_devices([devices[key]])
                if key in devices:
                    devices[key].update_ha_state(True)
    return mysensors_callback


class GatewayWrapper(object):
    """Gateway wrapper class."""

    # pylint: disable=too-few-public-methods

    def __init__(self, gateway, version, optimistic):
        """Setup class attributes on instantiation.

        Args:
        gateway (mysensors.SerialGateway): Gateway to wrap.
        version (str): Version of mysensors API.
        optimistic (bool): Send values to actuators without feedback state.

        Attributes:
        _wrapped_gateway (mysensors.SerialGateway): Wrapped gateway.
        version (str): Version of mysensors API.
        platform_callbacks (list): Callback functions, one per platform.
        optimistic (bool): Send values to actuators without feedback state.
        __initialised (bool): True if GatewayWrapper is initialised.
        """
        self._wrapped_gateway = gateway
        self.version = version
        self.platform_callbacks = []
        self.optimistic = optimistic
        self.__initialised = True

    def __getattr__(self, name):
        """See if this object has attribute name."""
        # Do not use hasattr, it goes into infinite recurrsion
        if name in self.__dict__:
            # This object has the attribute.
            return getattr(self, name)
        # The wrapped object has the attribute.
        return getattr(self._wrapped_gateway, name)

    def __setattr__(self, name, value):
        """See if this object has attribute name then set to value."""
        if '_GatewayWrapper__initialised' not in self.__dict__:
            return object.__setattr__(self, name, value)
        elif name in self.__dict__:
            object.__setattr__(self, name, value)
        else:
            object.__setattr__(self._wrapped_gateway, name, value)

    def callback_factory(self):
        """Return a new callback function."""
        def node_update(update_type, node_id):
            """Callback for node updates from the MySensors gateway."""
            _LOGGER.debug('update %s: node %s', update_type, node_id)
            for callback in self.platform_callbacks:
                callback(self, node_id)

        return node_update


class MySensorsDeviceEntity(object):
    """Represent a MySensors entity."""

    # pylint: disable=too-many-arguments,too-many-instance-attributes

    def __init__(
            self, gateway, node_id, child_id, name, value_type, child_type):
        """
        Setup class attributes on instantiation.

        Args:
        gateway (GatewayWrapper): Gateway object.
        node_id (str): Id of node.
        child_id (str): Id of child.
        name (str): Entity name.
        value_type (str): Value type of child. Value is entity state.
        child_type (str): Child type of child.

        Attributes:
        gateway (GatewayWrapper): Gateway object.
        node_id (str): Id of node.
        child_id (str): Id of child.
        _name (str): Entity name.
        value_type (str): Value type of child. Value is entity state.
        child_type (str): Child type of child.
        battery_level (int): Node battery level.
        _values (dict): Child values. Non state values set as state attributes.
        mysensors (module): Mysensors main component module.
        """
        self.gateway = gateway
        self.node_id = node_id
        self.child_id = child_id
        self._name = name
        self.value_type = value_type
        self.child_type = child_type
        self.battery_level = 0
        self._values = {}

    @property
    def should_poll(self):
        """Mysensor gateway pushes its state to HA."""
        return False

    @property
    def name(self):
        """The name of this entity."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        address = getattr(self.gateway, 'server_address', None)
        if address:
            device = '{}:{}'.format(address[0], address[1])
        else:
            device = self.gateway.port
        attr = {
            ATTR_DEVICE: device,
            ATTR_NODE_ID: self.node_id,
            ATTR_CHILD_ID: self.child_id,
            ATTR_BATTERY_LEVEL: self.battery_level,
        }

        set_req = self.gateway.const.SetReq

        for value_type, value in self._values.items():
            try:
                attr[set_req(value_type).name] = value
            except ValueError:
                _LOGGER.error('value_type %s is not valid for mysensors '
                              'version %s', value_type,
                              self.gateway.version)
        return attr

    @property
    def available(self):
        """Return True if entity is available."""
        return self.value_type in self._values

    def update(self):
        """Update the controller with the latest value from a sensor."""
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        self.battery_level = node.battery_level
        set_req = self.gateway.const.SetReq
        for value_type, value in child.values.items():
            _LOGGER.debug(
                "%s: value_type %s, value = %s", self._name, value_type, value)
            if value_type in (set_req.V_ARMED, set_req.V_LIGHT,
                              set_req.V_LOCK_STATUS, set_req.V_TRIPPED):
                self._values[value_type] = (
                    STATE_ON if int(value) == 1 else STATE_OFF)
            else:
                self._values[value_type] = value
