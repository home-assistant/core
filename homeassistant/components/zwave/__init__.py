"""
Support for Z-Wave.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zwave/
"""
import logging
import os.path
import time
from pprint import pprint

import voluptuous as vol

from homeassistant.helpers import discovery
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, ATTR_LOCATION, ATTR_ENTITY_ID, CONF_CUSTOMIZE,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers.event import track_time_change
from homeassistant.util import convert, slugify
import homeassistant.config as conf_util
import homeassistant.helpers.config_validation as cv
from . import const

REQUIREMENTS = ['pydispatcher==2.0.5']

_LOGGER = logging.getLogger(__name__)

CONF_AUTOHEAL = 'autoheal'
CONF_DEBUG = 'debug'
CONF_POLLING_INTENSITY = 'polling_intensity'
CONF_POLLING_INTERVAL = 'polling_interval'
CONF_USB_STICK_PATH = 'usb_path'
CONF_CONFIG_PATH = 'config_path'

DEFAULT_CONF_AUTOHEAL = True
DEFAULT_CONF_USB_STICK_PATH = '/zwaveusbstick'
DEFAULT_POLLING_INTERVAL = 60000
DEFAULT_DEBUG = True
DOMAIN = 'zwave'

NETWORK = None

# List of tuple (DOMAIN, discovered service, supported command classes,
# value type, genre type, specific device class).
DISCOVERY_COMPONENTS = [
    ('sensor',
     [const.GENERIC_TYPE_WHATEVER],
     [const.SPECIFIC_TYPE_WHATEVER],
     [const.COMMAND_CLASS_SENSOR_MULTILEVEL,
      const.COMMAND_CLASS_METER,
      const.COMMAND_CLASS_ALARM,
      const.COMMAND_CLASS_SENSOR_ALARM],
     const.TYPE_WHATEVER,
     const.GENRE_USER),
    ('light',
     [const.GENERIC_TYPE_SWITCH_MULTILEVEL,
      const.GENERIC_TYPE_SWITCH_REMOTE],
     [const.SPECIFIC_TYPE_POWER_SWITCH_MULTILEVEL,
      const.SPECIFIC_TYPE_SCENE_SWITCH_MULTILEVEL,
      const.SPECIFIC_TYPE_NOT_USED],
     [const.COMMAND_CLASS_SWITCH_MULTILEVEL],
     const.TYPE_BYTE,
     const.GENRE_USER),
    ('switch',
     [const.GENERIC_TYPE_SENSOR_ALARM,
      const.GENERIC_TYPE_SENSOR_BINARY,
      const.GENERIC_TYPE_SWITCH_BINARY,
      const.GENERIC_TYPE_ENTRY_CONTROL,
      const.GENERIC_TYPE_SENSOR_MULTILEVEL,
      const.GENERIC_TYPE_SWITCH_MULTILEVEL,
      const.GENERIC_TYPE_SENSOR_NOTIFICATION,
      const.GENERIC_TYPE_GENERIC_CONTROLLER,
      const.GENERIC_TYPE_SWITCH_REMOTE,
      const.GENERIC_TYPE_REPEATER_SLAVE,
      const.GENERIC_TYPE_THERMOSTAT,
      const.GENERIC_TYPE_WALL_CONTROLLER],
     [const.SPECIFIC_TYPE_WHATEVER],
     [const.COMMAND_CLASS_SWITCH_BINARY],
     const.TYPE_BOOL,
     const.GENRE_USER),
    ('binary_sensor',
     [const.GENERIC_TYPE_SENSOR_ALARM,
      const.GENERIC_TYPE_SENSOR_BINARY,
      const.GENERIC_TYPE_SWITCH_BINARY,
      const.GENERIC_TYPE_METER,
      const.GENERIC_TYPE_SENSOR_MULTILEVEL,
      const.GENERIC_TYPE_SWITCH_MULTILEVEL,
      const.GENERIC_TYPE_SENSOR_NOTIFICATION,
      const.GENERIC_TYPE_THERMOSTAT],
     [const.SPECIFIC_TYPE_WHATEVER],
     [const.COMMAND_CLASS_SENSOR_BINARY],
     const.TYPE_BOOL,
     const.GENRE_USER),
    ('lock',
     [const.GENERIC_TYPE_ENTRY_CONTROL],
     [const.SPECIFIC_TYPE_ADVANCED_DOOR_LOCK,
      const.SPECIFIC_TYPE_SECURE_KEYPAD_DOOR_LOCK],
     [const.COMMAND_CLASS_DOOR_LOCK],
     const.TYPE_BOOL,
     const.GENRE_USER),
    ('cover',
     [const.GENERIC_TYPE_SWITCH_MULTILEVEL,
      const.GENERIC_TYPE_ENTRY_CONTROL],
     [const.SPECIFIC_TYPE_CLASS_A_MOTOR_CONTROL,
      const.SPECIFIC_TYPE_CLASS_B_MOTOR_CONTROL,
      const.SPECIFIC_TYPE_CLASS_C_MOTOR_CONTROL,
      const.SPECIFIC_TYPE_MOTOR_MULTIPOSITION,
      const.SPECIFIC_TYPE_SECURE_BARRIER_ADDON,
      const.SPECIFIC_TYPE_SECURE_DOOR],
     [const.COMMAND_CLASS_SWITCH_BINARY,
      const.COMMAND_CLASS_BARRIER_OPERATOR,
      const.COMMAND_CLASS_SWITCH_MULTILEVEL],
     const.TYPE_WHATEVER,
     const.GENRE_USER),
    ('climate',
     [const.GENERIC_TYPE_THERMOSTAT],
     [const.SPECIFIC_TYPE_WHATEVER],
     [const.COMMAND_CLASS_THERMOSTAT_SETPOINT],
     const.TYPE_WHATEVER,
     const.GENRE_WHATEVER),
]

RENAME_NODE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(const.ATTR_NAME): cv.string,
})
SET_CONFIG_PARAMETER_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(const.ATTR_CONFIG_PARAMETER): vol.Coerce(int),
    vol.Required(const.ATTR_CONFIG_VALUE): vol.Coerce(int),
    vol.Optional(const.ATTR_CONFIG_SIZE): vol.Coerce(int)
})

CUSTOMIZE_SCHEMA = vol.Schema({
    vol.Optional(CONF_POLLING_INTENSITY):
        vol.All(cv.positive_int, vol.In([0, 1, 2, 3, 4, 5])),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_AUTOHEAL, default=DEFAULT_CONF_AUTOHEAL): cv.boolean,
        vol.Optional(CONF_CONFIG_PATH): cv.string,
        vol.Optional(CONF_CUSTOMIZE, default={}):
            vol.Schema({cv.string: CUSTOMIZE_SCHEMA}),
        vol.Optional(CONF_DEBUG, default=False): cv.boolean,
        vol.Optional(CONF_POLLING_INTERVAL, default=DEFAULT_POLLING_INTERVAL):
            cv.positive_int,
        vol.Optional(CONF_USB_STICK_PATH, default=DEFAULT_CONF_USB_STICK_PATH):
            cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def _obj_to_dict(obj):
    """Convert an object into a hash for debug."""
    return {key: getattr(obj, key) for key
            in dir(obj)
            if key[0] != '_' and not hasattr(getattr(obj, key), '__call__')}


def _node_name(node):
    """Return the name of the node."""
    return node.name or '{} {}'.format(
        node.manufacturer_name, node.product_name)


def _value_name(value):
    """Return the name of the value."""
    return '{} {}'.format(_node_name(value.node), value.label)


def _node_object_id(node):
    """Return the object_id of the node."""
    node_object_id = '{}_{}'.format(slugify(_node_name(node)), node.node_id)
    return node_object_id


def _object_id(value):
    """Return the object_id of the device value.

    The object_id contains node_id and value instance id
    to not collide with other entity_ids.
    """
    object_id = "{}_{}".format(slugify(_value_name(value)), value.node.node_id)

    # Add the instance id if there is more than one instance for the value
    if value.instance > 1:
        return '{}_{}'.format(object_id, value.instance)
    return object_id


def nice_print_node(node):
    """Print a nice formatted node to the output (debug method)."""
    node_dict = _obj_to_dict(node)
    node_dict['values'] = {value_id: _obj_to_dict(value)
                           for value_id, value in node.values.items()}

    print("\n\n\n")
    print("FOUND NODE", node.product_name)
    pprint(node_dict)
    print("\n\n\n")


def get_config_value(node, value_index):
    """Return the current configuration value for a specific index."""
    try:
        for value in node.values.values():
            # 112 == config command class
            if value.command_class == 112 and value.index == value_index:
                return value.data
    except RuntimeError:
        # If we get an runtime error the dict has changed while
        # we was looking for a value, just do it again
        return get_config_value(node, value_index)


# pylint: disable=R0914
def setup(hass, config):
    """Setup Z-Wave.

    Will automatically load components to support devices found on the network.
    """
    # pylint: disable=global-statement, import-error
    global NETWORK

    descriptions = conf_util.load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    try:
        import libopenzwave
    except ImportError:
        _LOGGER.error("You are missing required dependency Python Open "
                      "Z-Wave. Please follow instructions at: "
                      "https://home-assistant.io/components/zwave/")
        return False
    from pydispatch import dispatcher
    from openzwave.option import ZWaveOption
    from openzwave.network import ZWaveNetwork

    default_zwave_config_path = os.path.join(os.path.dirname(
        libopenzwave.__file__), 'config')

    # Load configuration
    use_debug = config[DOMAIN].get(CONF_DEBUG)
    customize = config[DOMAIN].get(CONF_CUSTOMIZE)
    autoheal = config[DOMAIN].get(CONF_AUTOHEAL)

    # Setup options
    options = ZWaveOption(
        config[DOMAIN].get(CONF_USB_STICK_PATH),
        user_path=hass.config.config_dir,
        config_path=config[DOMAIN].get(
            CONF_CONFIG_PATH, default_zwave_config_path))

    options.set_console_output(use_debug)
    options.lock()

    NETWORK = ZWaveNetwork(options, autostart=False)

    if use_debug:
        def log_all(signal, value=None):
            """Log all the signals."""
            print("")
            print("SIGNAL *****", signal)
            if value and signal in (ZWaveNetwork.SIGNAL_VALUE_CHANGED,
                                    ZWaveNetwork.SIGNAL_VALUE_ADDED,
                                    ZWaveNetwork.SIGNAL_SCENE_EVENT,
                                    ZWaveNetwork.SIGNAL_NODE_EVENT,
                                    ZWaveNetwork.SIGNAL_AWAKE_NODES_QUERIED,
                                    ZWaveNetwork.SIGNAL_ALL_NODES_QUERIED):
                pprint(_obj_to_dict(value))

            print("")

        dispatcher.connect(log_all, weak=False)

    def value_added(node, value):
        """Called when a value is added to a node on the network."""
        for (component,
             generic_device_class,
             specific_device_class,
             command_class,
             value_type,
             value_genre) in DISCOVERY_COMPONENTS:

            _LOGGER.debug("Component=%s Node_id=%s query start",
                          component, node.node_id)
            if node.generic not in generic_device_class and \
               None not in generic_device_class:
                _LOGGER.debug("node.generic %s not None and in "
                              "generic_device_class %s",
                              node.generic, generic_device_class)
                continue
            if node.specific not in specific_device_class and \
               None not in specific_device_class:
                _LOGGER.debug("node.specific %s is not None and in "
                              "specific_device_class %s", node.specific,
                              specific_device_class)
                continue
            if value.command_class not in command_class and \
               None not in command_class:
                _LOGGER.debug("value.command_class %s is not None "
                              "and in command_class %s",
                              value.command_class, command_class)
                continue
            if value_type != value.type and value_type is not None:
                _LOGGER.debug("value.type %s != value_type %s",
                              value.type, value_type)
                continue
            if value_genre != value.genre and value_genre is not None:
                _LOGGER.debug("value.genre %s != value_genre %s",
                              value.genre, value_genre)
                continue

            # Configure node
            _LOGGER.debug("Adding Node_id=%s Generic_command_class=%s, "
                          "Specific_command_class=%s, "
                          "Command_class=%s, Value type=%s, "
                          "Genre=%s", node.node_id,
                          node.generic, node.specific,
                          value.command_class, value.type,
                          value.genre)
            name = "{}.{}".format(component, _object_id(value))

            node_config = customize.get(name, {})
            polling_intensity = convert(
                node_config.get(CONF_POLLING_INTENSITY), int)
            if polling_intensity:
                value.enable_poll(polling_intensity)
            else:
                value.disable_poll()

            discovery.load_platform(hass, component, DOMAIN, {
                const.ATTR_NODE_ID: node.node_id,
                const.ATTR_VALUE_ID: value.value_id,
            }, config)

    def scene_activated(node, scene_id):
        """Called when a scene is activated on any node in the network."""
        hass.bus.fire(const.EVENT_SCENE_ACTIVATED, {
            ATTR_ENTITY_ID: _node_object_id(node),
            const.ATTR_OBJECT_ID: _node_object_id(node),
            const.ATTR_SCENE_ID: scene_id
        })

    def node_event_activated(node, value):
        """Called when a nodeevent is activated on any node in the network."""
        hass.bus.fire(const.EVENT_NODE_EVENT, {
            const.ATTR_OBJECT_ID: _node_object_id(node),
            const.ATTR_BASIC_LEVEL: value
        })

    def network_ready():
        """Called when all awake nodes have been queried."""
        _LOGGER.info("Zwave network is ready for use. All awake nodes"
                     " have been queried. Sleeping nodes will be"
                     " queried when they awake.")
        hass.bus.fire(const.EVENT_NETWORK_READY)

    def network_complete():
        """Called when all nodes on network have been queried."""
        _LOGGER.info("Zwave network is complete. All nodes on the network"
                     " have been queried")
        hass.bus.fire(const.EVENT_NETWORK_COMPLETE)

    dispatcher.connect(
        value_added, ZWaveNetwork.SIGNAL_VALUE_ADDED, weak=False)
    dispatcher.connect(
        scene_activated, ZWaveNetwork.SIGNAL_SCENE_EVENT, weak=False)
    dispatcher.connect(
        node_event_activated, ZWaveNetwork.SIGNAL_NODE_EVENT, weak=False)
    dispatcher.connect(
        network_ready, ZWaveNetwork.SIGNAL_AWAKE_NODES_QUERIED, weak=False)
    dispatcher.connect(
        network_complete, ZWaveNetwork.SIGNAL_ALL_NODES_QUERIED, weak=False)

    def add_node(service):
        """Switch into inclusion mode."""
        _LOGGER.info("Zwave add_node have been initialized.")
        NETWORK.controller.add_node()

    def add_node_secure(service):
        """Switch into secure inclusion mode."""
        _LOGGER.info("Zwave add_node_secure have been initialized.")
        NETWORK.controller.add_node(True)

    def remove_node(service):
        """Switch into exclusion mode."""
        _LOGGER.info("Zwave remove_node have been initialized.")
        NETWORK.controller.remove_node()

    def cancel_command(service):
        """Cancel a running controller command."""
        _LOGGER.info("Cancel running ZWave command.")
        NETWORK.controller.cancel_command()

    def heal_network(service):
        """Heal the network."""
        _LOGGER.info("ZWave heal running.")
        NETWORK.heal()

    def soft_reset(service):
        """Soft reset the controller."""
        _LOGGER.info("Zwave soft_reset have been initialized.")
        NETWORK.controller.soft_reset()

    def test_network(service):
        """Test the network by sending commands to all the nodes."""
        _LOGGER.info("Zwave test_network have been initialized.")
        NETWORK.test()

    def stop_zwave(_service_or_event):
        """Stop Z-Wave network."""
        _LOGGER.info("Stopping ZWave network.")
        NETWORK.stop()
        hass.bus.fire(const.EVENT_NETWORK_STOP)

    def rename_node(service):
        """Rename a node."""
        state = hass.states.get(service.data.get(ATTR_ENTITY_ID))
        node_id = state.attributes.get(const.ATTR_NODE_ID)
        node = NETWORK.nodes[node_id]
        name = service.data.get(const.ATTR_NAME)
        node.name = name
        _LOGGER.info(
            "Renamed ZWave node %d to %s", node_id, name)

    def set_config_parameter(service):
        """Set a config parameter to a node."""
        state = hass.states.get(service.data.get(ATTR_ENTITY_ID))
        node_id = state.attributes.get(const.ATTR_NODE_ID)
        node = NETWORK.nodes[node_id]
        param = service.data.get(const.ATTR_CONFIG_PARAMETER)
        value = service.data.get(const.ATTR_CONFIG_VALUE)
        size = service.data.get(const.ATTR_CONFIG_SIZE, 2)
        node.set_config_param(param, value, size)
        _LOGGER.info("Setting config parameter %s on Node %s "
                     "with value %s and size=%s", param, node_id, value, size)

    def start_zwave(_service_or_event):
        """Startup Z-Wave network."""
        _LOGGER.info("Starting ZWave network.")
        NETWORK.start()
        hass.bus.fire(const.EVENT_NETWORK_START)

        # Need to be in STATE_AWAKED before talking to nodes.
        # Wait up to NETWORK_READY_WAIT_SECS seconds for the zwave network
        # to be ready.
        for i in range(const.NETWORK_READY_WAIT_SECS):
            _LOGGER.debug(
                "network state: %d %s", NETWORK.state, NETWORK.state_str)
            if NETWORK.state >= NETWORK.STATE_AWAKED:
                _LOGGER.info("zwave ready after %d seconds", i)
                break
            time.sleep(1)
        else:
            _LOGGER.warning(
                "zwave not ready after %d seconds, continuing anyway",
                const.NETWORK_READY_WAIT_SECS)
            _LOGGER.info(
                "final network state: %d %s", NETWORK.state, NETWORK.state_str)

        polling_interval = convert(
            config[DOMAIN].get(CONF_POLLING_INTERVAL), int)
        if polling_interval is not None:
            NETWORK.set_poll_interval(polling_interval, False)

        poll_interval = NETWORK.get_poll_interval()
        _LOGGER.info("zwave polling interval set to %d ms", poll_interval)

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_zwave)

        # Register node services for Z-Wave network
        hass.services.register(DOMAIN, const.SERVICE_ADD_NODE, add_node,
                               descriptions[const.SERVICE_ADD_NODE])
        hass.services.register(DOMAIN, const.SERVICE_ADD_NODE_SECURE,
                               add_node_secure,
                               descriptions[const.SERVICE_ADD_NODE_SECURE])
        hass.services.register(DOMAIN, const.SERVICE_REMOVE_NODE, remove_node,
                               descriptions[const.SERVICE_REMOVE_NODE])
        hass.services.register(DOMAIN, const.SERVICE_CANCEL_COMMAND,
                               cancel_command,
                               descriptions[const.SERVICE_CANCEL_COMMAND])
        hass.services.register(DOMAIN, const.SERVICE_HEAL_NETWORK,
                               heal_network,
                               descriptions[const.SERVICE_HEAL_NETWORK])
        hass.services.register(DOMAIN, const.SERVICE_SOFT_RESET, soft_reset,
                               descriptions[const.SERVICE_SOFT_RESET])
        hass.services.register(DOMAIN, const.SERVICE_TEST_NETWORK,
                               test_network,
                               descriptions[const.SERVICE_TEST_NETWORK])
        hass.services.register(DOMAIN, const.SERVICE_STOP_NETWORK, stop_zwave,
                               descriptions[const.SERVICE_STOP_NETWORK])
        hass.services.register(DOMAIN, const.SERVICE_START_NETWORK,
                               start_zwave,
                               descriptions[const.SERVICE_START_NETWORK])
        hass.services.register(DOMAIN, const.SERVICE_RENAME_NODE, rename_node,
                               descriptions[const.SERVICE_RENAME_NODE],
                               schema=RENAME_NODE_SCHEMA)
        hass.services.register(DOMAIN, const.SERVICE_SET_CONFIG_PARAMETER,
                               set_config_parameter,
                               descriptions[
                                   const.SERVICE_SET_CONFIG_PARAMETER],
                               schema=SET_CONFIG_PARAMETER_SCHEMA)

    # Setup autoheal
    if autoheal:
        _LOGGER.info("ZWave network autoheal is enabled.")
        track_time_change(hass, heal_network, hour=0, minute=0, second=0)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_zwave)

    return True


class ZWaveDeviceEntity:
    """Representation of a Z-Wave node entity."""

    def __init__(self, value, domain):
        """Initialize the z-Wave device."""
        self._value = value
        self.entity_id = "{}.{}".format(domain, self._object_id())

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return an unique ID."""
        return "ZWAVE-{}-{}".format(self._value.node.node_id,
                                    self._value.object_id)

    @property
    def name(self):
        """Return the name of the device."""
        return _value_name(self._value)

    def _object_id(self):
        """Return the object_id of the device value.

        The object_id contains node_id and value instance id to not collide
        with other entity_ids.
        """
        return _object_id(self._value)

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        attrs = {
            const.ATTR_NODE_ID: self._value.node.node_id,
        }

        battery_level = self._value.node.get_battery_level()

        if battery_level is not None:
            attrs[ATTR_BATTERY_LEVEL] = battery_level

        location = self._value.node.location

        if location:
            attrs[ATTR_LOCATION] = location

        return attrs
