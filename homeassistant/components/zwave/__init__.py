"""
Support for Z-Wave.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zwave/
"""
import asyncio
import logging
import os.path
import time
from pprint import pprint

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.loader import get_platform
from homeassistant.helpers import discovery
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, ATTR_LOCATION, ATTR_ENTITY_ID, ATTR_WAKEUP,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_values import EntityValues
from homeassistant.helpers.event import track_time_change
from homeassistant.util import convert, slugify
import homeassistant.config as conf_util
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)

from . import const
from . import workaround
from .util import value_handler

REQUIREMENTS = ['pydispatcher==2.0.5']

_LOGGER = logging.getLogger(__name__)

CLASS_ID = 'class_id'
CONF_AUTOHEAL = 'autoheal'
CONF_DEBUG = 'debug'
CONF_POLLING_INTENSITY = 'polling_intensity'
CONF_POLLING_INTERVAL = 'polling_interval'
CONF_USB_STICK_PATH = 'usb_path'
CONF_CONFIG_PATH = 'config_path'
CONF_IGNORED = 'ignored'
CONF_REFRESH_VALUE = 'refresh_value'
CONF_REFRESH_DELAY = 'delay'
CONF_DEVICE_CONFIG = 'device_config'
CONF_DEVICE_CONFIG_GLOB = 'device_config_glob'
CONF_DEVICE_CONFIG_DOMAIN = 'device_config_domain'

ATTR_POWER = 'power_consumption'

DEFAULT_CONF_AUTOHEAL = True
DEFAULT_CONF_USB_STICK_PATH = '/zwaveusbstick'
DEFAULT_POLLING_INTERVAL = 60000
DEFAULT_DEBUG = False
DEFAULT_CONF_IGNORED = False
DEFAULT_CONF_REFRESH_VALUE = False
DEFAULT_CONF_REFRESH_DELAY = 5
DOMAIN = 'zwave'

DATA_ZWAVE_DICT = 'zwave_devices'

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
      const.COMMAND_CLASS_SENSOR_ALARM,
      const.COMMAND_CLASS_BATTERY],
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
    vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
    vol.Required(const.ATTR_CONFIG_PARAMETER): vol.Coerce(int),
    vol.Required(const.ATTR_CONFIG_VALUE): vol.Coerce(int),
    vol.Optional(const.ATTR_CONFIG_SIZE): vol.Coerce(int)
})
PRINT_CONFIG_PARAMETER_SCHEMA = vol.Schema({
    vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
    vol.Required(const.ATTR_CONFIG_PARAMETER): vol.Coerce(int),
})

NODE_SERVICE_SCHEMA = vol.Schema({
    vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
})

REFRESH_ENTITY_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
})

CHANGE_ASSOCIATION_SCHEMA = vol.Schema({
    vol.Required(const.ATTR_ASSOCIATION): cv.string,
    vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
    vol.Required(const.ATTR_TARGET_NODE_ID): vol.Coerce(int),
    vol.Required(const.ATTR_GROUP): vol.Coerce(int),
    vol.Optional(const.ATTR_INSTANCE, default=0x00): vol.Coerce(int)
})

SET_WAKEUP_SCHEMA = vol.Schema({
    vol.Required(const.ATTR_NODE_ID): vol.Coerce(int),
    vol.Required(const.ATTR_CONFIG_VALUE):
        vol.All(vol.Coerce(int), cv.positive_int),
})

DEVICE_CONFIG_SCHEMA_ENTRY = vol.Schema({
    vol.Optional(CONF_POLLING_INTENSITY): cv.positive_int,
    vol.Optional(CONF_IGNORED, default=DEFAULT_CONF_IGNORED): cv.boolean,
    vol.Optional(CONF_REFRESH_VALUE, default=DEFAULT_CONF_REFRESH_VALUE):
        cv.boolean,
    vol.Optional(CONF_REFRESH_DELAY, default=DEFAULT_CONF_REFRESH_DELAY):
        cv.positive_int
})

SIGNAL_REFRESH_ENTITY_FORMAT = 'zwave_refresh_entity_{}'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_AUTOHEAL, default=DEFAULT_CONF_AUTOHEAL): cv.boolean,
        vol.Optional(CONF_CONFIG_PATH): cv.string,
        vol.Optional(CONF_DEVICE_CONFIG, default={}):
            vol.Schema({cv.entity_id: DEVICE_CONFIG_SCHEMA_ENTRY}),
        vol.Optional(CONF_DEVICE_CONFIG_GLOB, default={}):
            vol.Schema({cv.string: DEVICE_CONFIG_SCHEMA_ENTRY}),
        vol.Optional(CONF_DEVICE_CONFIG_DOMAIN, default={}):
            vol.Schema({cv.string: DEVICE_CONFIG_SCHEMA_ENTRY}),
        vol.Optional(CONF_DEBUG, default=DEFAULT_DEBUG): cv.boolean,
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


def object_id(value):
    """Return the object_id of the device value.

    The object_id contains node_id and value instance id
    to not collide with other entity_ids.
    """
    _object_id = "{}_{}_{}".format(slugify(_value_name(value)),
                                   value.node.node_id, value.index)

    # Add the instance id if there is more than one instance for the value
    if value.instance > 1:
        return '{}_{}'.format(_object_id, value.instance)
    return _object_id


def nice_print_node(node):
    """Print a nice formatted node to the output (debug method)."""
    node_dict = _obj_to_dict(node)
    node_dict['values'] = {value_id: _obj_to_dict(value)
                           for value_id, value in node.values.items()}

    print("\n\n\n")
    print("FOUND NODE", node.product_name)
    pprint(node_dict)
    print("\n\n\n")


def get_config_value(node, value_index, tries=5):
    """Return the current configuration value for a specific index."""
    try:
        for value in node.values.values():
            # 112 == config command class
            if value.command_class == 112 and value.index == value_index:
                return value.data
    except RuntimeError:
        # If we get an runtime error the dict has changed while
        # we was looking for a value, just do it again
        return None if tries <= 0 else get_config_value(
            node, value_index, tries=tries - 1)
    return None


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Generic Z-Wave platform setup."""
    if discovery_info is None or NETWORK is None:
        return False
    device = hass.data[DATA_ZWAVE_DICT].pop(
        discovery_info[const.DISCOVERY_DEVICE])
    if device:
        async_add_devices([device])
        return True
    else:
        return False


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
    from openzwave.group import ZWaveGroup

    default_zwave_config_path = os.path.join(os.path.dirname(
        libopenzwave.__file__), 'config')

    # Load configuration
    use_debug = config[DOMAIN].get(CONF_DEBUG)
    autoheal = config[DOMAIN].get(CONF_AUTOHEAL)
    device_config = EntityValues(
        config[DOMAIN][CONF_DEVICE_CONFIG],
        config[DOMAIN][CONF_DEVICE_CONFIG_DOMAIN],
        config[DOMAIN][CONF_DEVICE_CONFIG_GLOB])

    # Setup options
    options = ZWaveOption(
        config[DOMAIN].get(CONF_USB_STICK_PATH),
        user_path=hass.config.config_dir,
        config_path=config[DOMAIN].get(
            CONF_CONFIG_PATH, default_zwave_config_path))

    options.set_console_output(use_debug)
    options.lock()

    NETWORK = ZWaveNetwork(options, autostart=False)
    hass.data[DATA_ZWAVE_DICT] = {}

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
                          "Genre=%s as %s", node.node_id,
                          node.generic, node.specific,
                          value.command_class, value.type,
                          value.genre, component)
            workaround_component = workaround.get_device_component_mapping(
                value)
            if workaround_component and workaround_component != component:
                if workaround_component == workaround.WORKAROUND_IGNORE:
                    _LOGGER.info("Ignoring device %s due to workaround.",
                                 "{}.{}".format(component, object_id(value)))
                    continue
                _LOGGER.debug("Using %s instead of %s",
                              workaround_component, component)
                component = workaround_component

            name = "{}.{}".format(component, object_id(value))
            node_config = device_config.get(name)

            if node_config.get(CONF_IGNORED):
                _LOGGER.info(
                    "Ignoring device %s due to device settings.", name)
                return

            polling_intensity = convert(
                node_config.get(CONF_POLLING_INTENSITY), int)
            if polling_intensity:
                value.enable_poll(polling_intensity)
            else:
                value.disable_poll()
            platform = get_platform(component, DOMAIN)
            device = platform.get_device(
                node=node, value=value, node_config=node_config, hass=hass)
            if not device:
                continue
            dict_id = value.value_id

            @asyncio.coroutine
            def discover_device(component, device, dict_id):
                """Put device in a dictionary and call discovery on it."""
                hass.data[DATA_ZWAVE_DICT][dict_id] = device
                yield from discovery.async_load_platform(
                    hass, component, DOMAIN,
                    {const.DISCOVERY_DEVICE: dict_id}, config)
            hass.add_job(discover_device, component, device, dict_id)

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
        if hass.state == 'RUNNING':
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

    def remove_failed_node(service):
        """Remove failed node."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        _LOGGER.info('Trying to remove zwave node %d', node_id)
        NETWORK.controller.remove_failed_node(node_id)

    def replace_failed_node(service):
        """Replace failed node."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        _LOGGER.info('Trying to replace zwave node %d', node_id)
        NETWORK.controller.replace_failed_node(node_id)

    def set_config_parameter(service):
        """Set a config parameter to a node."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        node = NETWORK.nodes[node_id]
        param = service.data.get(const.ATTR_CONFIG_PARAMETER)
        selection = service.data.get(const.ATTR_CONFIG_VALUE)
        size = service.data.get(const.ATTR_CONFIG_SIZE, 2)
        i = 0
        for value in (
                node.get_values(class_id=const.COMMAND_CLASS_CONFIGURATION)
                .values()):
            if value.index == param and value.type == const.TYPE_LIST:
                _LOGGER.debug('Values for parameter %s: %s', param,
                              value.data_items)
                i = len(value.data_items) - 1
        if i == 0:
            node.set_config_param(param, selection, size)
        else:
            if selection > i:
                _LOGGER.info('Config parameter selection does not exist!'
                             ' Please check zwcfg_[home_id].xml in'
                             ' your homeassistant config directory. '
                             ' Available selections are 0 to %s', i)
                return
            node.set_config_param(param, selection, size)
            _LOGGER.info('Setting config parameter %s on Node %s '
                         'with selection %s and size=%s', param, node_id,
                         selection, size)

    def print_config_parameter(service):
        """Print a config parameter from a node."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        node = NETWORK.nodes[node_id]
        param = service.data.get(const.ATTR_CONFIG_PARAMETER)
        _LOGGER.info("Config parameter %s on Node %s : %s",
                     param, node_id, get_config_value(node, param))

    def print_node(service):
        """Print all information about z-wave node."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        node = NETWORK.nodes[node_id]
        nice_print_node(node)

    def set_wakeup(service):
        """Set wake-up interval of a node."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        node = NETWORK.nodes[node_id]
        value = service.data.get(const.ATTR_CONFIG_VALUE)
        if node.can_wake_up():
            for value_id in node.get_values(
                    class_id=const.COMMAND_CLASS_WAKE_UP):
                node.values[value_id].data = value
                _LOGGER.info("Node %s wake-up set to %d", node_id, value)
        else:
            _LOGGER.info("Node %s is not wakeable", node_id)

    def change_association(service):
        """Change an association in the zwave network."""
        association_type = service.data.get(const.ATTR_ASSOCIATION)
        node_id = service.data.get(const.ATTR_NODE_ID)
        target_node_id = service.data.get(const.ATTR_TARGET_NODE_ID)
        group = service.data.get(const.ATTR_GROUP)
        instance = service.data.get(const.ATTR_INSTANCE)

        node = ZWaveGroup(group, NETWORK, node_id)
        if association_type == 'add':
            node.add_association(target_node_id, instance)
            _LOGGER.info("Adding association for node:%s in group:%s "
                         "target node:%s, instance=%s", node_id, group,
                         target_node_id, instance)
        if association_type == 'remove':
            node.remove_association(target_node_id, instance)
            _LOGGER.info("Removing association for node:%s in group:%s "
                         "target node:%s, instance=%s", node_id, group,
                         target_node_id, instance)

    @asyncio.coroutine
    def async_refresh_entity(service):
        """Refresh values that specific entity depends on."""
        entity_id = service.data.get(ATTR_ENTITY_ID)
        async_dispatcher_send(
            hass, SIGNAL_REFRESH_ENTITY_FORMAT.format(entity_id))

    def refresh_node(service):
        """Refresh all node info."""
        node_id = service.data.get(const.ATTR_NODE_ID)
        node = NETWORK.nodes[node_id]
        node.refresh_info()

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
        hass.services.register(DOMAIN, const.SERVICE_PRINT_CONFIG_PARAMETER,
                               print_config_parameter,
                               descriptions[
                                   const.SERVICE_PRINT_CONFIG_PARAMETER],
                               schema=PRINT_CONFIG_PARAMETER_SCHEMA)
        hass.services.register(DOMAIN, const.SERVICE_REMOVE_FAILED_NODE,
                               remove_failed_node,
                               descriptions[const.SERVICE_REMOVE_FAILED_NODE],
                               schema=NODE_SERVICE_SCHEMA)
        hass.services.register(DOMAIN, const.SERVICE_REPLACE_FAILED_NODE,
                               replace_failed_node,
                               descriptions[const.SERVICE_REPLACE_FAILED_NODE],
                               schema=NODE_SERVICE_SCHEMA)

        hass.services.register(DOMAIN, const.SERVICE_CHANGE_ASSOCIATION,
                               change_association,
                               descriptions[
                                   const.SERVICE_CHANGE_ASSOCIATION],
                               schema=CHANGE_ASSOCIATION_SCHEMA)
        hass.services.register(DOMAIN, const.SERVICE_SET_WAKEUP,
                               set_wakeup,
                               descriptions[
                                   const.SERVICE_SET_WAKEUP],
                               schema=SET_WAKEUP_SCHEMA)
        hass.services.register(DOMAIN, const.SERVICE_PRINT_NODE,
                               print_node,
                               descriptions[
                                   const.SERVICE_PRINT_NODE],
                               schema=NODE_SERVICE_SCHEMA)
        hass.services.register(DOMAIN, const.SERVICE_REFRESH_ENTITY,
                               async_refresh_entity,
                               descriptions[
                                   const.SERVICE_REFRESH_ENTITY],
                               schema=REFRESH_ENTITY_SCHEMA)
        hass.services.register(DOMAIN, const.SERVICE_REFRESH_NODE,
                               refresh_node,
                               descriptions[
                                   const.SERVICE_REFRESH_NODE],
                               schema=NODE_SERVICE_SCHEMA)

    # Setup autoheal
    if autoheal:
        _LOGGER.info("ZWave network autoheal is enabled.")
        track_time_change(hass, heal_network, hour=0, minute=0, second=0)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_zwave)

    return True


class ZWaveDeviceEntity(Entity):
    """Representation of a Z-Wave node entity."""

    def __init__(self, value, domain):
        """Initialize the z-Wave device."""
        # pylint: disable=import-error
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher
        self._value = value
        self._value.set_change_verified(False)
        self.entity_id = "{}.{}".format(domain, object_id(value))

        self._name = _value_name(self._value)
        self._unique_id = "ZWAVE-{}-{}".format(self._value.node.node_id,
                                               self._value.object_id)
        self._wakeup_value_id = None
        self._battery_value_id = None
        self._power_value_id = None
        self._update_scheduled = False
        self._update_attributes()

        dispatcher.connect(
            self.network_value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)

    def network_value_changed(self, value):
        """Called when a value has changed on the network."""
        if self._value.value_id == value.value_id:
            return self.value_changed()

        dependent_ids = self._get_dependent_value_ids()
        if dependent_ids is None and self._value.node == value.node:
            return self.value_changed()
        if dependent_ids is not None and value.value_id in dependent_ids:
            return self.value_changed()

    def value_changed(self):
        """Called when a value for this entity's node has changed."""
        if not self._value.node.is_ready:
            self._update_ids()
        self._update_attributes()
        self.update_properties()
        # If value changed after device was created but before setup_platform
        # was called - skip updating state.
        if self.hass and not self._update_scheduled:
            self.hass.add_job(self._schedule_update)

    def _update_ids(self):
        """Update value_ids from which to pull attributes."""
        if self._wakeup_value_id is None:
            self._wakeup_value_id = self.get_value(
                class_id=const.COMMAND_CLASS_WAKE_UP, member='value_id')
        if self._battery_value_id is None:
            self._battery_value_id = self.get_value(
                class_id=const.COMMAND_CLASS_BATTERY, member='value_id')
        if self._power_value_id is None:
            self._power_value_id = self.get_value(
                class_id=[const.COMMAND_CLASS_SENSOR_MULTILEVEL,
                          const.COMMAND_CLASS_METER],
                label=['Power'], member='value_id',
                instance=self._value.instance)

    @property
    def dependent_value_ids(self):
        """List of value IDs a device depends on.

        None if depends on the whole node.
        """
        return []

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Add device to dict."""
        async_dispatcher_connect(
            self.hass,
            SIGNAL_REFRESH_ENTITY_FORMAT.format(self.entity_id),
            self.refresh_from_network)

    def _get_dependent_value_ids(self):
        """Return a list of value_ids this device depend on.

        Return None if it depends on the whole node.
        """
        if self.dependent_value_ids is None:
            # Device depends on node.
            return None
        if not self._value.node.is_ready:
            # Node is not ready, so depend on the whole node.
            return None

        return [val for val in (self.dependent_value_ids + [
            self._wakeup_value_id, self._battery_value_id,
            self._power_value_id]) if val]

    def _update_attributes(self):
        """Update the node attributes. May only be used inside callback."""
        self.node_id = self._value.node.node_id
        self.location = self._value.node.location
        self.battery_level = self._value.node.get_battery_level(
            self._battery_value_id)
        self.wakeup_interval = None
        if self._wakeup_value_id:
            self.wakeup_interval = self._value.node.values[
                self._wakeup_value_id].data
        power_value = None
        if self._power_value_id:
            power_value = self._value.node.values[self._power_value_id]
        self.power_consumption = round(
            power_value.data, power_value.precision) if power_value else None

    def get_value(self, **kwargs):
        """Simplifyer to get values. May only be used inside callback."""
        return value_handler(self._value, method='get', **kwargs)

    def set_value(self, **kwargs):
        """Simplifyer to set a value."""
        return value_handler(self._value, method='set', **kwargs)

    def update_properties(self):
        """Callback on data changes for node values."""
        pass

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        attrs = {
            const.ATTR_NODE_ID: self.node_id,
        }

        if self.battery_level is not None:
            attrs[ATTR_BATTERY_LEVEL] = self.battery_level

        if self.location:
            attrs[ATTR_LOCATION] = self.location

        if self.wakeup_interval is not None:
            attrs[ATTR_WAKEUP] = self.wakeup_interval

        if self.power_consumption is not None:
            attrs[ATTR_POWER] = self.power_consumption

        return attrs

    def refresh_from_network(self):
        """Refresh all dependent values from zwave network."""
        dependent_ids = self._get_dependent_value_ids()
        if dependent_ids is None:
            # Entity depends on the whole node
            self._value.node.refresh_info()
            return
        for value_id in dependent_ids + [self._value.value_id]:
            self._value.node.refresh_value(value_id)

    @callback
    def _schedule_update(self):
        """Schedule delayed update."""
        if self._update_scheduled:
            return

        @callback
        def do_update():
            """Really update."""
            self.hass.async_add_job(self.async_update_ha_state)
            self._update_scheduled = False

        self._update_scheduled = True
        self.hass.loop.call_later(0.1, do_update)
