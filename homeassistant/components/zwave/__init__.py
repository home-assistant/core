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
    ATTR_BATTERY_LEVEL, ATTR_LOCATION, ATTR_ENTITY_ID,
    CONF_CUSTOMIZE, EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers.event import track_time_change
from homeassistant.util import convert, slugify
import homeassistant.config as conf_util
import homeassistant.helpers.config_validation as cv
# pylint: disable=wildcard-import
from .const import * # noqa F403

DOMAIN = "zwave"
REQUIREMENTS = ['pydispatcher==2.0.5']

CONF_USB_STICK_PATH = "usb_path"
DEFAULT_CONF_USB_STICK_PATH = "/zwaveusbstick"
CONF_DEBUG = "debug"
CONF_POLLING_INTERVAL = "polling_interval"
CONF_POLLING_INTENSITY = "polling_intensity"
CONF_AUTOHEAL = "autoheal"
DEFAULT_CONF_AUTOHEAL = True


# List of tuple (DOMAIN, discovered service, supported command classes,
# value type, genre type, specific device class).
DISCOVERY_COMPONENTS = [
    ('sensor',
     [GENERIC_TYPE_WHATEVER], # noqa F405
     [SPECIFIC_TYPE_WHATEVER], # noqa F405
     [COMMAND_CLASS_SENSOR_MULTILEVEL, # noqa F405
      COMMAND_CLASS_METER, # noqa F405
      COMMAND_CLASS_ALARM, # noqa F405
      COMMAND_CLASS_SENSOR_ALARM], # noqa F405
     TYPE_WHATEVER, # noqa F405
     GENRE_USER), # noqa F405
    ('light',
     [GENERIC_TYPE_SWITCH_MULTILEVEL, # noqa F405
      GENERIC_TYPE_SWITCH_REMOTE], # noqa F405
     [SPECIFIC_TYPE_POWER_SWITCH_MULTILEVEL, # noqa F405
      SPECIFIC_TYPE_SCENE_SWITCH_MULTILEVEL, # noqa F405
      SPECIFIC_TYPE_NOT_USED], # noqa F405
     [COMMAND_CLASS_SWITCH_MULTILEVEL], # noqa F405
     TYPE_BYTE, # noqa F405
     GENRE_USER), # noqa F405
    ('switch',
     [GENERIC_TYPE_SENSOR_ALARM, # noqa F405
      GENERIC_TYPE_SENSOR_BINARY, # noqa F405
      GENERIC_TYPE_SWITCH_BINARY, # noqa F405
      GENERIC_TYPE_ENTRY_CONTROL, # noqa F405
      GENERIC_TYPE_SENSOR_MULTILEVEL, # noqa F405
      GENERIC_TYPE_SWITCH_MULTILEVEL, # noqa F405
      GENERIC_TYPE_SENSOR_NOTIFICATION, # noqa F405
      GENERIC_TYPE_GENERIC_CONTROLLER, # noqa F405
      GENERIC_TYPE_SWITCH_REMOTE, # noqa F405
      GENERIC_TYPE_REPEATER_SLAVE, # noqa F405
      GENERIC_TYPE_THERMOSTAT, # noqa F405
      GENERIC_TYPE_WALL_CONTROLLER], # noqa F405
     [SPECIFIC_TYPE_WHATEVER], # noqa F405
     [COMMAND_CLASS_SWITCH_BINARY], # noqa F405
     TYPE_BOOL, # noqa F405
     GENRE_USER), # noqa F405
    ('binary_sensor',
     [GENERIC_TYPE_SENSOR_ALARM, # noqa F405
      GENERIC_TYPE_SENSOR_BINARY, # noqa F405
      GENERIC_TYPE_SWITCH_BINARY, # noqa F405
      GENERIC_TYPE_METER, # noqa F405
      GENERIC_TYPE_SENSOR_MULTILEVEL, # noqa F405
      GENERIC_TYPE_SWITCH_MULTILEVEL, # noqa F405
      GENERIC_TYPE_SENSOR_NOTIFICATION, # noqa F405
      GENERIC_TYPE_THERMOSTAT], # noqa F405
     [SPECIFIC_TYPE_WHATEVER], # noqa F405
     [COMMAND_CLASS_SENSOR_BINARY], # noqa F405
     TYPE_BOOL, # noqa F405
     GENRE_USER), # noqa F405
    ('lock',
     [GENERIC_TYPE_ENTRY_CONTROL], # noqa F405
     [SPECIFIC_TYPE_ADVANCED_DOOR_LOCK, # noqa F405
      SPECIFIC_TYPE_SECURE_KEYPAD_DOOR_LOCK], # noqa F405
     [COMMAND_CLASS_DOOR_LOCK], # noqa F405
     TYPE_BOOL, # noqa F405
     GENRE_USER), # noqa F405
    ('cover',
     [GENERIC_TYPE_SWITCH_MULTILEVEL, # noqa F405
      GENERIC_TYPE_ENTRY_CONTROL], # noqa F405
     [SPECIFIC_TYPE_CLASS_A_MOTOR_CONTROL, # noqa F405
      SPECIFIC_TYPE_CLASS_B_MOTOR_CONTROL, # noqa F405
      SPECIFIC_TYPE_CLASS_C_MOTOR_CONTROL, # noqa F405
      SPECIFIC_TYPE_MOTOR_MULTIPOSITION, # noqa F405
      SPECIFIC_TYPE_SECURE_BARRIER_ADDON, # noqa F405
      SPECIFIC_TYPE_SECURE_DOOR], # noqa F405
     [COMMAND_CLASS_SWITCH_BINARY, # noqa F405
      COMMAND_CLASS_BARRIER_OPERATOR, # noqa F405
      COMMAND_CLASS_SWITCH_MULTILEVEL], # noqa F405
     TYPE_WHATEVER, # noqa F405
     GENRE_USER), # noqa F405
    ('climate',
     [GENERIC_TYPE_THERMOSTAT], # noqa F405
     [SPECIFIC_TYPE_WHATEVER], # noqa F405
     [COMMAND_CLASS_THERMOSTAT_SETPOINT], # noqa F405
     TYPE_WHATEVER, # noqa F405
     GENRE_WHATEVER), # noqa F405
]


ATTR_NODE_ID = "node_id"
ATTR_VALUE_ID = "value_id"
ATTR_OBJECT_ID = "object_id"
ATTR_NAME = "name"
ATTR_SCENE_ID = "scene_id"
ATTR_BASIC_LEVEL = "basic_level"

RENAME_NODE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_NAME): cv.string,
})

NETWORK = None

_LOGGER = logging.getLogger(__name__)


def _obj_to_dict(obj):
    """Convert an object into a hash for debug."""
    return {key: getattr(obj, key) for key
            in dir(obj)
            if key[0] != '_' and not hasattr(getattr(obj, key), '__call__')}


def _node_name(node):
    """Return the name of the node."""
    return node.name or "{} {}".format(
        node.manufacturer_name, node.product_name)


def _value_name(value):
    """Return the name of the value."""
    return "{} {}".format(_node_name(value.node), value.label)


def _node_object_id(node):
    """Return the object_id of the node."""
    node_object_id = "{}_{}".format(slugify(_node_name(node)),
                                    node.node_id)

    return node_object_id


def _object_id(value):
    """Return the object_id of the device value.

    The object_id contains node_id and value instance id
    to not collide with other entity_ids.
    """
    object_id = "{}_{}".format(slugify(_value_name(value)),
                               value.node.node_id)

    # Add the instance id if there is more than one instance for the value
    if value.instance > 1:
        return "{}_{}".format(object_id, value.instance)

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
        os.path.join(os.path.dirname(__file__), "services.yaml"))

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
    use_debug = str(config[DOMAIN].get(CONF_DEBUG)) == '1'
    customize = config[DOMAIN].get(CONF_CUSTOMIZE, {})
    autoheal = config[DOMAIN].get(CONF_AUTOHEAL, DEFAULT_CONF_AUTOHEAL)

    # Setup options
    options = ZWaveOption(
        config[DOMAIN].get(CONF_USB_STICK_PATH, DEFAULT_CONF_USB_STICK_PATH),
        user_path=hass.config.config_dir,
        config_path=config[DOMAIN].get('config_path',
                                       default_zwave_config_path),)

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
                ATTR_NODE_ID: node.node_id,
                ATTR_VALUE_ID: value.value_id,
            }, config)

    def scene_activated(node, scene_id):
        """Called when a scene is activated on any node in the network."""
        hass.bus.fire(EVENT_SCENE_ACTIVATED, { # noqa F405
            ATTR_ENTITY_ID: _node_object_id(node),
            ATTR_OBJECT_ID: _node_object_id(node),
            ATTR_SCENE_ID: scene_id
        })

    def node_event_activated(node, value):
        """Called when a nodeevent is activated on any node in the network."""
        hass.bus.fire(EVENT_NODE_EVENT, { # noqa F405
            ATTR_OBJECT_ID: _node_object_id(node),
            ATTR_BASIC_LEVEL: value
        })

    def network_ready():
        """Called when all awake nodes have been queried."""
        _LOGGER.info("Zwave network is ready for use. All awake nodes"
                     " have been queried. Sleeping nodes will be"
                     " queried when they awake.")
        hass.bus.fire(EVENT_NETWORK_READY)  # noqa F405

    def network_complete():
        """Called when all nodes on network have been queried."""
        _LOGGER.info("Zwave network is complete. All nodes on the network"
                     " have been queried")
        hass.bus.fire(EVENT_NETWORK_COMPLETE)  # noqa F405

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
        hass.bus.fire(EVENT_NETWORK_STOP) # noqa F405

    def rename_node(service):
        """Rename a node."""
        state = hass.states.get(service.data.get(ATTR_ENTITY_ID))
        node_id = state.attributes.get(ATTR_NODE_ID)
        node = NETWORK.nodes[node_id]
        name = service.data.get(ATTR_NAME)
        node.name = name
        _LOGGER.info(
            "Renamed ZWave node %d to %s", node_id, name)

    def start_zwave(_service_or_event):
        """Startup Z-Wave network."""
        _LOGGER.info("Starting ZWave network.")
        NETWORK.start()
        hass.bus.fire(EVENT_NETWORK_START) # noqa F405

        # Need to be in STATE_AWAKED before talking to nodes.
        # Wait up to NETWORK_READY_WAIT_SECS seconds for the zwave network
        # to be ready.
        for i in range(NETWORK_READY_WAIT_SECS): # noqa F405
            _LOGGER.debug(
                "network state: %d %s", NETWORK.state, NETWORK.state_str)
            if NETWORK.state >= NETWORK.STATE_AWAKED:
                _LOGGER.info("zwave ready after %d seconds", i)
                break
            time.sleep(1)
        else:
            _LOGGER.warning(
                "zwave not ready after %d seconds, continuing anyway",
                NETWORK_READY_WAIT_SECS) # noqa F405
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
        hass.services.register(DOMAIN, SERVICE_ADD_NODE, add_node) # noqa F405
        hass.services.register(DOMAIN, SERVICE_ADD_NODE_SECURE, # noqa F405
                               add_node_secure)
        hass.services.register(DOMAIN, SERVICE_REMOVE_NODE, remove_node) # noqa F405
        hass.services.register(DOMAIN, SERVICE_CANCEL_COMMAND, cancel_command) # noqa F405
        hass.services.register(DOMAIN, SERVICE_HEAL_NETWORK, heal_network) # noqa F405
        hass.services.register(DOMAIN, SERVICE_SOFT_RESET, soft_reset) # noqa F405
        hass.services.register(DOMAIN, SERVICE_TEST_NETWORK, test_network) # noqa F405
        hass.services.register(DOMAIN, SERVICE_STOP_NETWORK, stop_zwave) # noqa F405
        hass.services.register(DOMAIN, SERVICE_START_NETWORK, start_zwave) # noqa F405
        hass.services.register(DOMAIN, SERVICE_RENAME_NODE, rename_node, # noqa F405
                               descriptions[DOMAIN][SERVICE_RENAME_NODE], # noqa F405
                               schema=RENAME_NODE_SCHEMA)

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
            ATTR_NODE_ID: self._value.node.node_id,
        }

        battery_level = self._value.node.get_battery_level()

        if battery_level is not None:
            attrs[ATTR_BATTERY_LEVEL] = battery_level

        location = self._value.node.location

        if location:
            attrs[ATTR_LOCATION] = location

        return attrs
