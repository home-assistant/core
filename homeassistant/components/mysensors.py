"""
Connect to a MySensors gateway via pymysensors API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mysensors/
"""
import logging
import os
import socket
import sys

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.setup import setup_component
from homeassistant.components.mqtt import (
    valid_publish_topic, valid_subscribe_topic)
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, CONF_NAME, CONF_OPTIMISTIC, EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP, STATE_OFF, STATE_ON)
from homeassistant.helpers import discovery
from homeassistant.loader import get_component

REQUIREMENTS = ['pymysensors==0.10.0']

_LOGGER = logging.getLogger(__name__)

ATTR_CHILD_ID = 'child_id'
ATTR_DESCRIPTION = 'description'
ATTR_DEVICE = 'device'
ATTR_NODE_ID = 'node_id'

CONF_BAUD_RATE = 'baud_rate'
CONF_DEBUG = 'debug'
CONF_DEVICE = 'device'
CONF_GATEWAYS = 'gateways'
CONF_PERSISTENCE = 'persistence'
CONF_PERSISTENCE_FILE = 'persistence_file'
CONF_RETAIN = 'retain'
CONF_TCP_PORT = 'tcp_port'
CONF_TOPIC_IN_PREFIX = 'topic_in_prefix'
CONF_TOPIC_OUT_PREFIX = 'topic_out_prefix'
CONF_VERSION = 'version'

DEFAULT_BAUD_RATE = 115200
DEFAULT_TCP_PORT = 5003
DEFAULT_VERSION = 1.4
DOMAIN = 'mysensors'

MQTT_COMPONENT = 'mqtt'
MYSENSORS_GATEWAYS = 'mysensors_gateways'


def is_socket_address(value):
    """Validate that value is a valid address."""
    try:
        socket.getaddrinfo(value, None)
        return value
    except OSError:
        raise vol.Invalid('Device is not a valid domain name or ip address')


def has_parent_dir(value):
    """Validate that value is in an existing directory which is writetable."""
    parent = os.path.dirname(os.path.realpath(value))
    is_dir_writable = os.path.isdir(parent) and os.access(parent, os.W_OK)
    if not is_dir_writable:
        raise vol.Invalid(
            '{} directory does not exist or is not writetable'.format(parent))
    return value


def has_all_unique_files(value):
    """Validate that all persistence files are unique and set if any is set."""
    persistence_files = [
        gateway.get(CONF_PERSISTENCE_FILE) for gateway in value]
    if None in persistence_files and any(
            name is not None for name in persistence_files):
        raise vol.Invalid(
            'persistence file name of all devices must be set if any is set')
    if not all(name is None for name in persistence_files):
        schema = vol.Schema(vol.Unique())
        schema(persistence_files)
    return value


def is_persistence_file(value):
    """Validate that persistence file path ends in either .pickle or .json."""
    if value.endswith(('.json', '.pickle')):
        return value
    else:
        raise vol.Invalid(
            '{} does not end in either `.json` or `.pickle`'.format(value))


def is_serial_port(value):
    """Validate that value is a windows serial port or a unix device."""
    if sys.platform.startswith('win'):
        ports = ('COM{}'.format(idx + 1) for idx in range(256))
        if value in ports:
            return value
        else:
            raise vol.Invalid(
                '{} is not a serial port'.format(value))
    else:
        return cv.isdevice(value)


def deprecated(key):
    """Mark key as deprecated in config."""
    def validator(config):
        """Check if key is in config, log warning and remove key."""
        if key not in config:
            return config
        _LOGGER.warning(
            '%s option for %s is deprecated. Please remove %s from your '
            'configuration file.', key, DOMAIN, key)
        config.pop(key)
        return config
    return validator


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema(vol.All(deprecated(CONF_DEBUG), {
        vol.Required(CONF_GATEWAYS): vol.All(
            cv.ensure_list, has_all_unique_files,
            [{
                vol.Required(CONF_DEVICE):
                    vol.Any(MQTT_COMPONENT, is_socket_address, is_serial_port),
                vol.Optional(CONF_PERSISTENCE_FILE):
                    vol.All(cv.string, is_persistence_file, has_parent_dir),
                vol.Optional(
                    CONF_BAUD_RATE,
                    default=DEFAULT_BAUD_RATE): cv.positive_int,
                vol.Optional(
                    CONF_TCP_PORT,
                    default=DEFAULT_TCP_PORT): cv.port,
                vol.Optional(
                    CONF_TOPIC_IN_PREFIX, default=''): valid_subscribe_topic,
                vol.Optional(
                    CONF_TOPIC_OUT_PREFIX, default=''): valid_publish_topic,
            }]
        ),
        vol.Optional(CONF_OPTIMISTIC, default=False): cv.boolean,
        vol.Optional(CONF_PERSISTENCE, default=True): cv.boolean,
        vol.Optional(CONF_RETAIN, default=True): cv.boolean,
        vol.Optional(CONF_VERSION, default=DEFAULT_VERSION): vol.Coerce(float),
    }))
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the MySensors component."""
    import mysensors.mysensors as mysensors

    version = config[DOMAIN].get(CONF_VERSION)
    persistence = config[DOMAIN].get(CONF_PERSISTENCE)

    def setup_gateway(device, persistence_file, baud_rate, tcp_port, in_prefix,
                      out_prefix):
        """Return gateway after setup of the gateway."""
        if device == MQTT_COMPONENT:
            if not setup_component(hass, MQTT_COMPONENT, config):
                return
            mqtt = get_component(MQTT_COMPONENT)
            retain = config[DOMAIN].get(CONF_RETAIN)

            def pub_callback(topic, payload, qos, retain):
                """Call MQTT publish function."""
                mqtt.publish(hass, topic, payload, qos, retain)

            def sub_callback(topic, callback, qos):
                """Call MQTT subscribe function."""
                mqtt.subscribe(hass, topic, callback, qos)
            gateway = mysensors.MQTTGateway(
                pub_callback, sub_callback,
                event_callback=None, persistence=persistence,
                persistence_file=persistence_file,
                protocol_version=version, in_prefix=in_prefix,
                out_prefix=out_prefix, retain=retain)
        else:
            try:
                is_serial_port(device)
                gateway = mysensors.SerialGateway(
                    device, event_callback=None, persistence=persistence,
                    persistence_file=persistence_file,
                    protocol_version=version, baud=baud_rate)
            except vol.Invalid:
                try:
                    socket.getaddrinfo(device, None)
                    # valid ip address
                    gateway = mysensors.TCPGateway(
                        device, event_callback=None, persistence=persistence,
                        persistence_file=persistence_file,
                        protocol_version=version, port=tcp_port)
                except OSError:
                    # invalid ip address
                    return
        gateway.metric = hass.config.units.is_metric
        optimistic = config[DOMAIN].get(CONF_OPTIMISTIC)
        gateway = GatewayWrapper(gateway, optimistic, device)
        # pylint: disable=attribute-defined-outside-init
        gateway.event_callback = gateway.callback_factory()

        def gw_start(event):
            """Trigger to start of the gateway and any persistence."""
            if persistence:
                for node_id in gateway.sensors:
                    node = gateway.sensors[node_id]
                    for child_id in node.children:
                        msg = mysensors.Message().modify(
                            node_id=node_id, child_id=child_id)
                        gateway.event_callback(msg)
            gateway.start()
            hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                                 lambda event: gateway.stop())

        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, gw_start)

        return gateway

    gateways = hass.data.get(MYSENSORS_GATEWAYS)
    if gateways is not None:
        _LOGGER.error(
            "%s already exists in %s, will not setup %s component",
            MYSENSORS_GATEWAYS, hass.data, DOMAIN)
        return False

    # Setup all devices from config
    gateways = []
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
        ready_gateway = setup_gateway(
            device, persistence_file, baud_rate, tcp_port, in_prefix,
            out_prefix)
        if ready_gateway is not None:
            gateways.append(ready_gateway)

    if not gateways:
        _LOGGER.error(
            "No devices could be setup as gateways, check your configuration")
        return False

    hass.data[MYSENSORS_GATEWAYS] = gateways

    for component in ['sensor', 'switch', 'light', 'binary_sensor', 'climate',
                      'cover']:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    discovery.load_platform(
        hass, 'device_tracker', DOMAIN, {}, config)

    discovery.load_platform(
        hass, 'notify', DOMAIN, {CONF_NAME: DOMAIN}, config)

    return True


def pf_callback_factory(map_sv_types, devices, entity_class, add_devices=None):
    """Return a new callback for the platform."""
    def mysensors_callback(gateway, msg):
        """Run when a message from the gateway arrives."""
        if gateway.sensors[msg.node_id].sketch_name is None:
            _LOGGER.debug("No sketch_name: node %s", msg.node_id)
            return
        child = gateway.sensors[msg.node_id].children.get(msg.child_id)
        if child is None:
            return
        for value_type in child.values:
            key = msg.node_id, child.id, value_type
            if child.type not in map_sv_types or \
                    value_type not in map_sv_types[child.type]:
                continue
            if key in devices:
                if add_devices:
                    devices[key].schedule_update_ha_state(True)
                else:
                    devices[key].update()
                continue
            name = '{} {} {}'.format(
                gateway.sensors[msg.node_id].sketch_name, msg.node_id,
                child.id)
            if isinstance(entity_class, dict):
                device_class = entity_class[child.type]
            else:
                device_class = entity_class
            devices[key] = device_class(
                gateway, msg.node_id, child.id, name, value_type)
            if add_devices:
                _LOGGER.info("Adding new devices: %s", [devices[key]])
                add_devices([devices[key]], True)
            else:
                devices[key].update()
    return mysensors_callback


class GatewayWrapper(object):
    """Gateway wrapper class."""

    def __init__(self, gateway, optimistic, device):
        """Set up the class attributes on instantiation.

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
        def node_update(msg):
            """Handle node updates from the MySensors gateway."""
            _LOGGER.debug(
                "Update: node %s, child %s sub_type %s",
                msg.node_id, msg.child_id, msg.sub_type)
            for callback in self.platform_callbacks:
                callback(self, msg)

        return node_update


class MySensorsDeviceEntity(object):
    """Representation of a MySensors entity."""

    def __init__(self, gateway, node_id, child_id, name, value_type):
        """Set up the MySensors device."""
        self.gateway = gateway
        self.node_id = node_id
        self.child_id = child_id
        self._name = name
        self.value_type = value_type
        child = gateway.sensors[node_id].children[child_id]
        self.child_type = child.type
        self._values = {}

    @property
    def should_poll(self):
        """Mysensor gateway pushes its state to HA."""
        return False

    @property
    def name(self):
        """Return the name of this entity."""
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
                _LOGGER.error("Value_type %s is not valid for mysensors "
                              "version %s", value_type,
                              self.gateway.protocol_version)
        return attr

    @property
    def available(self):
        """Return true if entity is available."""
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
            elif value_type == set_req.V_DIMMER:
                self._values[value_type] = int(value)
            else:
                self._values[value_type] = value
