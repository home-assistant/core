"""
Connect to a MySensors gateway via pymysensors API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mysensors/
"""
import logging
import socket

import voluptuous as vol

from homeassistant.bootstrap import setup_component
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (ATTR_BATTERY_LEVEL, CONF_OPTIMISTIC,
                                 EVENT_HOMEASSISTANT_START,
                                 EVENT_HOMEASSISTANT_STOP, STATE_OFF, STATE_ON)
from homeassistant.helpers import discovery
from homeassistant.loader import get_component

_LOGGER = logging.getLogger(__name__)

ATTR_NODE_ID = 'node_id'
ATTR_CHILD_ID = 'child_id'
ATTR_DESCRIPTION = 'description'
ATTR_DEVICE = 'device'
CONF_BAUD_RATE = 'baud_rate'
CONF_DEVICE = 'device'
CONF_DEBUG = 'debug'
CONF_GATEWAYS = 'gateways'
CONF_PERSISTENCE = 'persistence'
CONF_PERSISTENCE_FILE = 'persistence_file'
CONF_TCP_PORT = 'tcp_port'
CONF_TOPIC_IN_PREFIX = 'topic_in_prefix'
CONF_TOPIC_OUT_PREFIX = 'topic_out_prefix'
CONF_RETAIN = 'retain'
CONF_VERSION = 'version'
DEFAULT_VERSION = 1.4
DEFAULT_BAUD_RATE = 115200
DEFAULT_TCP_PORT = 5003
DOMAIN = 'mysensors'
GATEWAYS = None
MQTT_COMPONENT = 'mqtt'
REQUIREMENTS = [
    'https://github.com/theolind/pymysensors/archive/'
    '8ce98b7fb56f7921a808eb66845ce8b2c455c81e.zip#pymysensors==0.7.1']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_GATEWAYS): vol.All(cv.ensure_list, [
            {
                vol.Required(CONF_DEVICE): cv.string,
                vol.Optional(CONF_PERSISTENCE_FILE): cv.string,
                vol.Optional(
                    CONF_BAUD_RATE,
                    default=DEFAULT_BAUD_RATE): cv.positive_int,
                vol.Optional(
                    CONF_TCP_PORT,
                    default=DEFAULT_TCP_PORT): cv.port,
                vol.Optional(CONF_TOPIC_IN_PREFIX, default=''): cv.string,
                vol.Optional(CONF_TOPIC_OUT_PREFIX, default=''): cv.string,
            },
        ]),
        vol.Optional(CONF_DEBUG, default=False): cv.boolean,
        vol.Optional(CONF_OPTIMISTIC, default=False): cv.boolean,
        vol.Optional(CONF_PERSISTENCE, default=True): cv.boolean,
        vol.Optional(CONF_RETAIN, default=True): cv.boolean,
        vol.Optional(CONF_VERSION, default=DEFAULT_VERSION): vol.Coerce(float),
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):  # pylint: disable=too-many-locals
    """Setup the MySensors component."""
    import mysensors.mysensors as mysensors

    version = config[DOMAIN].get(CONF_VERSION)
    persistence = config[DOMAIN].get(CONF_PERSISTENCE)

    def setup_gateway(device, persistence_file, baud_rate, tcp_port, in_prefix,
                      out_prefix):
        """Return gateway after setup of the gateway."""
        # pylint: disable=too-many-arguments
        if device == MQTT_COMPONENT:
            if not setup_component(hass, MQTT_COMPONENT, config):
                return
            mqtt = get_component(MQTT_COMPONENT)
            retain = config[DOMAIN].get(CONF_RETAIN)

            def pub_callback(topic, payload, qos, retain):
                """Call mqtt publish function."""
                mqtt.publish(hass, topic, payload, qos, retain)

            def sub_callback(topic, callback, qos):
                """Call mqtt subscribe function."""
                mqtt.subscribe(hass, topic, callback, qos)
            gateway = mysensors.MQTTGateway(
                pub_callback, sub_callback,
                event_callback=None, persistence=persistence,
                persistence_file=persistence_file,
                protocol_version=version, in_prefix=in_prefix,
                out_prefix=out_prefix, retain=retain)
        else:
            try:
                socket.inet_aton(device)
                # valid ip address
                gateway = mysensors.TCPGateway(
                    device, event_callback=None, persistence=persistence,
                    persistence_file=persistence_file,
                    protocol_version=version, port=tcp_port)
            except OSError:
                # invalid ip address
                gateway = mysensors.SerialGateway(
                    device, event_callback=None, persistence=persistence,
                    persistence_file=persistence_file,
                    protocol_version=version, baud=baud_rate)
        gateway.metric = hass.config.units.is_metric
        gateway.debug = config[DOMAIN].get(CONF_DEBUG)
        optimistic = config[DOMAIN].get(CONF_OPTIMISTIC)
        gateway = GatewayWrapper(gateway, optimistic, device)
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

    for index, gway in enumerate(conf_gateways):
        device = gway[CONF_DEVICE]
        persistence_file = gway.get(
            CONF_PERSISTENCE_FILE,
            hass.config.path('mysensors{}.pickle'.format(index + 1)))
        baud_rate = gway.get(CONF_BAUD_RATE)
        tcp_port = gway.get(CONF_TCP_PORT)
        in_prefix = gway.get(CONF_TOPIC_IN_PREFIX)
        out_prefix = gway.get(CONF_TOPIC_OUT_PREFIX)
        GATEWAYS[device] = setup_gateway(
            device, persistence_file, baud_rate, tcp_port, in_prefix,
            out_prefix)
        if GATEWAYS[device] is None:
            GATEWAYS.pop(device)

    if not GATEWAYS:
        _LOGGER.error(
            'No devices could be setup as gateways, check your configuration')
        return False

    for component in 'sensor', 'switch', 'light', 'binary_sensor', 'climate':
        discovery.load_platform(hass, component, DOMAIN, {}, config)

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

    def __init__(self, gateway, optimistic, device):
        """Setup class attributes on instantiation.

        Args:
        gateway (mysensors.SerialGateway): Gateway to wrap.
        optimistic (bool): Send values to actuators without feedback state.
        device (str): Path to serial port, ip adress or mqtt.

        Attributes:
        _wrapped_gateway (mysensors.SerialGateway): Wrapped gateway.
        platform_callbacks (list): Callback functions, one per platform.
        optimistic (bool): Send values to actuators without feedback state.
        device (str): Device configured as gateway.
        __initialised (bool): True if GatewayWrapper is initialised.
        """
        self._wrapped_gateway = gateway
        self.platform_callbacks = []
        self.optimistic = optimistic
        self.device = device
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
            _LOGGER.debug('Update %s: node %s', update_type, node_id)
            for callback in self.platform_callbacks:
                callback(self, node_id)

        return node_update


class MySensorsDeviceEntity(object):
    """Represent a MySensors entity."""

    # pylint: disable=too-many-arguments

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
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        attr = {
            ATTR_BATTERY_LEVEL: node.battery_level,
            ATTR_CHILD_ID: self.child_id,
            ATTR_DESCRIPTION: child.description,
            ATTR_DEVICE: self.gateway.device,
            ATTR_NODE_ID: self.node_id,
        }

        set_req = self.gateway.const.SetReq

        for value_type, value in self._values.items():
            try:
                attr[set_req(value_type).name] = value
            except ValueError:
                _LOGGER.error('Value_type %s is not valid for mysensors '
                              'version %s', value_type,
                              self.gateway.protocol_version)
        return attr

    @property
    def available(self):
        """Return True if entity is available."""
        return self.value_type in self._values

    def update(self):
        """Update the controller with the latest value from a sensor."""
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
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
