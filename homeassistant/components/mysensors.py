"""
Connect to a MySensors gateway via pymysensors API.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mysensors/
"""
import asyncio
from collections import defaultdict
import logging
import os
import socket
import sys
from timeit import default_timer as timer

import voluptuous as vol

from homeassistant.components.mqtt import (
    valid_publish_topic, valid_subscribe_topic)
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, CONF_NAME, CONF_OPTIMISTIC, EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP, STATE_OFF, STATE_ON)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, dispatcher_send)
from homeassistant.helpers.entity import Entity
from homeassistant.loader import get_component
from homeassistant.setup import setup_component

REQUIREMENTS = ['pymysensors==0.11.1']

_LOGGER = logging.getLogger(__name__)

ATTR_CHILD_ID = 'child_id'
ATTR_DESCRIPTION = 'description'
ATTR_DEVICE = 'device'
ATTR_DEVICES = 'devices'
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

CONF_NODES = 'nodes'
CONF_NODE_NAME = 'name'

DEFAULT_BAUD_RATE = 115200
DEFAULT_TCP_PORT = 5003
DEFAULT_VERSION = '1.4'
DOMAIN = 'mysensors'

MQTT_COMPONENT = 'mqtt'
MYSENSORS_GATEWAYS = 'mysensors_gateways'
MYSENSORS_PLATFORM_DEVICES = 'mysensors_devices_{}'
PLATFORM = 'platform'
SCHEMA = 'schema'
SIGNAL_CALLBACK = 'mysensors_callback_{}_{}_{}_{}'
TYPE = 'type'


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
            raise vol.Invalid('{} is not a serial port'.format(value))
    else:
        return cv.isdevice(value)


def deprecated(key):
    """Mark key as deprecated in configuration."""
    def validator(config):
        """Check if key is in config, log warning and remove key."""
        if key not in config:
            return config
        _LOGGER.warning(
            '%s option for %s is deprecated. Please remove %s from your '
            'configuration file', key, DOMAIN, key)
        config.pop(key)
        return config
    return validator


NODE_SCHEMA = vol.Schema({
    cv.positive_int: {
        vol.Required(CONF_NODE_NAME): cv.string
    }
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema(vol.All(deprecated(CONF_DEBUG), {
        vol.Required(CONF_GATEWAYS): vol.All(
            cv.ensure_list, has_all_unique_files,
            [{
                vol.Required(CONF_DEVICE):
                    vol.Any(MQTT_COMPONENT, is_socket_address, is_serial_port),
                vol.Optional(CONF_PERSISTENCE_FILE):
                    vol.All(cv.string, is_persistence_file, has_parent_dir),
                vol.Optional(CONF_BAUD_RATE, default=DEFAULT_BAUD_RATE):
                    cv.positive_int,
                vol.Optional(CONF_TCP_PORT, default=DEFAULT_TCP_PORT): cv.port,
                vol.Optional(CONF_TOPIC_IN_PREFIX, default=''):
                    valid_subscribe_topic,
                vol.Optional(CONF_TOPIC_OUT_PREFIX, default=''):
                    valid_publish_topic,
                vol.Optional(CONF_NODES, default={}): NODE_SCHEMA,
            }]
        ),
        vol.Optional(CONF_OPTIMISTIC, default=False): cv.boolean,
        vol.Optional(CONF_PERSISTENCE, default=True): cv.boolean,
        vol.Optional(CONF_RETAIN, default=True): cv.boolean,
        vol.Optional(CONF_VERSION, default=DEFAULT_VERSION): cv.string,
    }))
}, extra=vol.ALLOW_EXTRA)


# MySensors const schemas
BINARY_SENSOR_SCHEMA = {PLATFORM: 'binary_sensor', TYPE: 'V_TRIPPED'}
CLIMATE_SCHEMA = {PLATFORM: 'climate', TYPE: 'V_HVAC_FLOW_STATE'}
LIGHT_DIMMER_SCHEMA = {
    PLATFORM: 'light', TYPE: 'V_DIMMER',
    SCHEMA: {'V_DIMMER': cv.string, 'V_LIGHT': cv.string}}
LIGHT_PERCENTAGE_SCHEMA = {
    PLATFORM: 'light', TYPE: 'V_PERCENTAGE',
    SCHEMA: {'V_PERCENTAGE': cv.string, 'V_STATUS': cv.string}}
LIGHT_RGB_SCHEMA = {
    PLATFORM: 'light', TYPE: 'V_RGB', SCHEMA: {
        'V_RGB': cv.string, 'V_STATUS': cv.string}}
LIGHT_RGBW_SCHEMA = {
    PLATFORM: 'light', TYPE: 'V_RGBW', SCHEMA: {
        'V_RGBW': cv.string, 'V_STATUS': cv.string}}
NOTIFY_SCHEMA = {PLATFORM: 'notify', TYPE: 'V_TEXT'}
DEVICE_TRACKER_SCHEMA = {PLATFORM: 'device_tracker', TYPE: 'V_POSITION'}
DUST_SCHEMA = [
    {PLATFORM: 'sensor', TYPE: 'V_DUST_LEVEL'},
    {PLATFORM: 'sensor', TYPE: 'V_LEVEL'}]
SWITCH_LIGHT_SCHEMA = {PLATFORM: 'switch', TYPE: 'V_LIGHT'}
SWITCH_STATUS_SCHEMA = {PLATFORM: 'switch', TYPE: 'V_STATUS'}
MYSENSORS_CONST_SCHEMA = {
    'S_DOOR': [BINARY_SENSOR_SCHEMA, {PLATFORM: 'switch', TYPE: 'V_ARMED'}],
    'S_MOTION': [BINARY_SENSOR_SCHEMA, {PLATFORM: 'switch', TYPE: 'V_ARMED'}],
    'S_SMOKE': [BINARY_SENSOR_SCHEMA, {PLATFORM: 'switch', TYPE: 'V_ARMED'}],
    'S_SPRINKLER': [
        BINARY_SENSOR_SCHEMA, {PLATFORM: 'switch', TYPE: 'V_STATUS'}],
    'S_WATER_LEAK': [
        BINARY_SENSOR_SCHEMA, {PLATFORM: 'switch', TYPE: 'V_ARMED'}],
    'S_SOUND': [
        BINARY_SENSOR_SCHEMA, {PLATFORM: 'sensor', TYPE: 'V_LEVEL'},
        {PLATFORM: 'switch', TYPE: 'V_ARMED'}],
    'S_VIBRATION': [
        BINARY_SENSOR_SCHEMA, {PLATFORM: 'sensor', TYPE: 'V_LEVEL'},
        {PLATFORM: 'switch', TYPE: 'V_ARMED'}],
    'S_MOISTURE': [
        BINARY_SENSOR_SCHEMA, {PLATFORM: 'sensor', TYPE: 'V_LEVEL'},
        {PLATFORM: 'switch', TYPE: 'V_ARMED'}],
    'S_HVAC': [CLIMATE_SCHEMA],
    'S_COVER': [
        {PLATFORM: 'cover', TYPE: 'V_DIMMER'},
        {PLATFORM: 'cover', TYPE: 'V_PERCENTAGE'},
        {PLATFORM: 'cover', TYPE: 'V_LIGHT'},
        {PLATFORM: 'cover', TYPE: 'V_STATUS'}],
    'S_DIMMER': [LIGHT_DIMMER_SCHEMA, LIGHT_PERCENTAGE_SCHEMA],
    'S_RGB_LIGHT': [LIGHT_RGB_SCHEMA],
    'S_RGBW_LIGHT': [LIGHT_RGBW_SCHEMA],
    'S_INFO': [NOTIFY_SCHEMA, {PLATFORM: 'sensor', TYPE: 'V_TEXT'}],
    'S_GPS': [
        DEVICE_TRACKER_SCHEMA, {PLATFORM: 'sensor', TYPE: 'V_POSITION'}],
    'S_TEMP': [{PLATFORM: 'sensor', TYPE: 'V_TEMP'}],
    'S_HUM': [{PLATFORM: 'sensor', TYPE: 'V_HUM'}],
    'S_BARO': [
        {PLATFORM: 'sensor', TYPE: 'V_PRESSURE'},
        {PLATFORM: 'sensor', TYPE: 'V_FORECAST'}],
    'S_WIND': [
        {PLATFORM: 'sensor', TYPE: 'V_WIND'},
        {PLATFORM: 'sensor', TYPE: 'V_GUST'},
        {PLATFORM: 'sensor', TYPE: 'V_DIRECTION'}],
    'S_RAIN': [
        {PLATFORM: 'sensor', TYPE: 'V_RAIN'},
        {PLATFORM: 'sensor', TYPE: 'V_RAINRATE'}],
    'S_UV': [{PLATFORM: 'sensor', TYPE: 'V_UV'}],
    'S_WEIGHT': [
        {PLATFORM: 'sensor', TYPE: 'V_WEIGHT'},
        {PLATFORM: 'sensor', TYPE: 'V_IMPEDANCE'}],
    'S_POWER': [
        {PLATFORM: 'sensor', TYPE: 'V_WATT'},
        {PLATFORM: 'sensor', TYPE: 'V_KWH'},
        {PLATFORM: 'sensor', TYPE: 'V_VAR'},
        {PLATFORM: 'sensor', TYPE: 'V_VA'},
        {PLATFORM: 'sensor', TYPE: 'V_POWER_FACTOR'}],
    'S_DISTANCE': [{PLATFORM: 'sensor', TYPE: 'V_DISTANCE'}],
    'S_LIGHT_LEVEL': [
        {PLATFORM: 'sensor', TYPE: 'V_LIGHT_LEVEL'},
        {PLATFORM: 'sensor', TYPE: 'V_LEVEL'}],
    'S_IR': [
        {PLATFORM: 'sensor', TYPE: 'V_IR_RECEIVE'},
        {PLATFORM: 'switch', TYPE: 'V_IR_SEND',
         SCHEMA: {'V_IR_SEND': cv.string, 'V_LIGHT': cv.string}}],
    'S_WATER': [
        {PLATFORM: 'sensor', TYPE: 'V_FLOW'},
        {PLATFORM: 'sensor', TYPE: 'V_VOLUME'}],
    'S_CUSTOM': [
        {PLATFORM: 'sensor', TYPE: 'V_VAR1'},
        {PLATFORM: 'sensor', TYPE: 'V_VAR2'},
        {PLATFORM: 'sensor', TYPE: 'V_VAR3'},
        {PLATFORM: 'sensor', TYPE: 'V_VAR4'},
        {PLATFORM: 'sensor', TYPE: 'V_VAR5'},
        {PLATFORM: 'sensor', TYPE: 'V_CUSTOM'}],
    'S_SCENE_CONTROLLER': [
        {PLATFORM: 'sensor', TYPE: 'V_SCENE_ON'},
        {PLATFORM: 'sensor', TYPE: 'V_SCENE_OFF'}],
    'S_COLOR_SENSOR': [{PLATFORM: 'sensor', TYPE: 'V_RGB'}],
    'S_MULTIMETER': [
        {PLATFORM: 'sensor', TYPE: 'V_VOLTAGE'},
        {PLATFORM: 'sensor', TYPE: 'V_CURRENT'},
        {PLATFORM: 'sensor', TYPE: 'V_IMPEDANCE'}],
    'S_GAS': [
        {PLATFORM: 'sensor', TYPE: 'V_FLOW'},
        {PLATFORM: 'sensor', TYPE: 'V_VOLUME'}],
    'S_WATER_QUALITY': [
        {PLATFORM: 'sensor', TYPE: 'V_TEMP'},
        {PLATFORM: 'sensor', TYPE: 'V_PH'},
        {PLATFORM: 'sensor', TYPE: 'V_ORP'},
        {PLATFORM: 'sensor', TYPE: 'V_EC'},
        {PLATFORM: 'switch', TYPE: 'V_STATUS'}],
    'S_AIR_QUALITY': DUST_SCHEMA,
    'S_DUST': DUST_SCHEMA,
    'S_LIGHT': [SWITCH_LIGHT_SCHEMA],
    'S_BINARY': [SWITCH_STATUS_SCHEMA],
    'S_LOCK': [{PLATFORM: 'switch', TYPE: 'V_LOCK_STATUS'}],
}


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
        gateway.optimistic = config[DOMAIN].get(CONF_OPTIMISTIC)
        gateway.device = device
        gateway.event_callback = gw_callback_factory(hass)

        def gw_start(event):
            """Trigger to start of the gateway and any persistence."""
            if persistence:
                discover_persistent_devices(hass, gateway)
            gateway.start()
            hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                                 lambda event: gateway.stop())

        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, gw_start)

        return gateway

    # Setup all devices from config
    gateways = {}
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
            ready_gateway.nodes_config = gway.get(CONF_NODES)
            gateways[id(ready_gateway)] = ready_gateway

    if not gateways:
        _LOGGER.error(
            "No devices could be setup as gateways, check your configuration")
        return False

    hass.data[MYSENSORS_GATEWAYS] = gateways

    return True


def validate_child(gateway, node_id, child):
    """Validate that a child has the correct values according to schema.

    Return a dict of platform with a list of device ids for validated devices.
    """
    validated = defaultdict(list)

    if not child.values:
        _LOGGER.debug(
            "No child values for node %s child %s", node_id, child.id)
        return validated
    if gateway.sensors[node_id].sketch_name is None:
        _LOGGER.debug("Node %s is missing sketch name", node_id)
        return validated
    pres = gateway.const.Presentation
    set_req = gateway.const.SetReq
    s_name = next(
        (member.name for member in pres if member.value == child.type), None)
    if s_name not in MYSENSORS_CONST_SCHEMA:
        _LOGGER.warning("Child type %s is not supported", s_name)
        return validated
    child_schemas = MYSENSORS_CONST_SCHEMA[s_name]

    def msg(name):
        """Return a message for an invalid schema."""
        return "{} requires value_type {}".format(
            pres(child.type).name, set_req[name].name)

    for schema in child_schemas:
        platform = schema[PLATFORM]
        v_name = schema[TYPE]
        value_type = next(
            (member.value for member in set_req if member.name == v_name),
            None)
        if value_type is None:
            continue
        _child_schema = child.get_schema(gateway.protocol_version)
        vol_schema = _child_schema.extend(
            {vol.Required(set_req[key].value, msg=msg(key)):
             _child_schema.schema.get(set_req[key].value, val)
             for key, val in schema.get(SCHEMA, {v_name: cv.string}).items()},
            extra=vol.ALLOW_EXTRA)
        try:
            vol_schema(child.values)
        except vol.Invalid as exc:
            level = (logging.WARNING if value_type in child.values
                     else logging.DEBUG)
            _LOGGER.log(
                level,
                "Invalid values: %s: %s platform: node %s child %s: %s",
                child.values, platform, node_id, child.id, exc)
            continue
        dev_id = id(gateway), node_id, child.id, value_type
        validated[platform].append(dev_id)
    return validated


def discover_mysensors_platform(hass, platform, new_devices):
    """Discover a MySensors platform."""
    discovery.load_platform(
        hass, platform, DOMAIN, {ATTR_DEVICES: new_devices, CONF_NAME: DOMAIN})


def discover_persistent_devices(hass, gateway):
    """Discover platforms for devices loaded via persistence file."""
    new_devices = defaultdict(list)
    for node_id in gateway.sensors:
        node = gateway.sensors[node_id]
        for child in node.children.values():
            validated = validate_child(gateway, node_id, child)
            for platform, dev_ids in validated.items():
                new_devices[platform].extend(dev_ids)
    for platform, dev_ids in new_devices.items():
        discover_mysensors_platform(hass, platform, dev_ids)


def get_mysensors_devices(hass, domain):
    """Return MySensors devices for a platform."""
    if MYSENSORS_PLATFORM_DEVICES.format(domain) not in hass.data:
        hass.data[MYSENSORS_PLATFORM_DEVICES.format(domain)] = {}
    return hass.data[MYSENSORS_PLATFORM_DEVICES.format(domain)]


def gw_callback_factory(hass):
    """Return a new callback for the gateway."""
    def mysensors_callback(msg):
        """Handle messages from a MySensors gateway."""
        start = timer()
        _LOGGER.debug(
            "Node update: node %s child %s", msg.node_id, msg.child_id)

        child = msg.gateway.sensors[msg.node_id].children.get(msg.child_id)
        if child is None:
            _LOGGER.debug("Not a child update for node %s", msg.node_id)
            return

        signals = []

        # Update all platforms for the device via dispatcher.
        # Add/update entity if schema validates to true.
        validated = validate_child(msg.gateway, msg.node_id, child)
        for platform, dev_ids in validated.items():
            devices = get_mysensors_devices(hass, platform)
            new_dev_ids = []
            for dev_id in dev_ids:
                if dev_id in devices:
                    signals.append(SIGNAL_CALLBACK.format(*dev_id))
                else:
                    new_dev_ids.append(dev_id)
            if new_dev_ids:
                discover_mysensors_platform(hass, platform, new_dev_ids)
        for signal in set(signals):
            # Only one signal per device is needed.
            # A device can have multiple platforms, ie multiple schemas.
            # FOR LATER: Add timer to not signal if another update comes in.
            dispatcher_send(hass, signal)
        end = timer()
        if end - start > 0.1:
            _LOGGER.debug(
                "Callback for node %s child %s took %.3f seconds",
                msg.node_id, msg.child_id, end - start)
    return mysensors_callback


def get_mysensors_name(gateway, node_id, child_id):
    """Return a name for a node child."""
    node_name = '{} {}'.format(
        gateway.sensors[node_id].sketch_name, node_id)
    node_name = next(
        (node[CONF_NODE_NAME] for conf_id, node in gateway.nodes_config.items()
         if node.get(CONF_NODE_NAME) is not None and conf_id == node_id),
        node_name)
    return '{} {}'.format(node_name, child_id)


def get_mysensors_gateway(hass, gateway_id):
    """Return MySensors gateway."""
    if MYSENSORS_GATEWAYS not in hass.data:
        hass.data[MYSENSORS_GATEWAYS] = {}
    gateways = hass.data.get(MYSENSORS_GATEWAYS)
    return gateways.get(gateway_id)


def setup_mysensors_platform(
        hass, domain, discovery_info, device_class, device_args=None,
        add_devices=None):
    """Set up a MySensors platform."""
    # Only act if called via MySensors by discovery event.
    # Otherwise gateway is not setup.
    if not discovery_info:
        return
    if device_args is None:
        device_args = ()
    new_devices = []
    new_dev_ids = discovery_info[ATTR_DEVICES]
    for dev_id in new_dev_ids:
        devices = get_mysensors_devices(hass, domain)
        if dev_id in devices:
            continue
        gateway_id, node_id, child_id, value_type = dev_id
        gateway = get_mysensors_gateway(hass, gateway_id)
        if not gateway:
            continue
        device_class_copy = device_class
        if isinstance(device_class, dict):
            child = gateway.sensors[node_id].children[child_id]
            s_type = gateway.const.Presentation(child.type).name
            device_class_copy = device_class[s_type]
        name = get_mysensors_name(gateway, node_id, child_id)

        # python 3.4 cannot unpack inside tuple, but combining tuples works
        args_copy = device_args + (
            gateway, node_id, child_id, name, value_type)
        devices[dev_id] = device_class_copy(*args_copy)
        new_devices.append(devices[dev_id])
    if new_devices:
        _LOGGER.info("Adding new devices: %s", new_devices)
        if add_devices is not None:
            add_devices(new_devices, True)
    return new_devices


class MySensorsDevice(object):
    """Representation of a MySensors device."""

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
            attr[set_req(value_type).name] = value

        return attr

    def update(self):
        """Update the controller with the latest value from a sensor."""
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        set_req = self.gateway.const.SetReq
        for value_type, value in child.values.items():
            _LOGGER.debug(
                "Entity update: %s: value_type %s, value = %s",
                self._name, value_type, value)
            if value_type in (set_req.V_ARMED, set_req.V_LIGHT,
                              set_req.V_LOCK_STATUS, set_req.V_TRIPPED):
                self._values[value_type] = (
                    STATE_ON if int(value) == 1 else STATE_OFF)
            elif value_type == set_req.V_DIMMER:
                self._values[value_type] = int(value)
            else:
                self._values[value_type] = value


class MySensorsEntity(MySensorsDevice, Entity):
    """Representation of a MySensors entity."""

    @property
    def should_poll(self):
        """Return the polling state. The gateway pushes its states."""
        return False

    @property
    def available(self):
        """Return true if entity is available."""
        return self.value_type in self._values

    def _async_update_callback(self):
        """Update the entity."""
        self.async_schedule_update_ha_state(True)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register update callback."""
        dev_id = id(self.gateway), self.node_id, self.child_id, self.value_type
        async_dispatcher_connect(
            self.hass, SIGNAL_CALLBACK.format(*dev_id),
            self._async_update_callback)
