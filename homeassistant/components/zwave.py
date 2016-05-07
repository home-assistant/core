"""
Support for Z-Wave.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zwave/
"""
import logging
import os.path
import time
from pprint import pprint

from homeassistant import bootstrap
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, ATTR_DISCOVERED, ATTR_ENTITY_ID, ATTR_LOCATION,
    ATTR_SERVICE, CONF_CUSTOMIZE, EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP, EVENT_PLATFORM_DISCOVERED)
from homeassistant.util import convert, slugify

DOMAIN = "zwave"
REQUIREMENTS = ['pydispatcher==2.0.5']

CONF_USB_STICK_PATH = "usb_path"
DEFAULT_CONF_USB_STICK_PATH = "/zwaveusbstick"
CONF_DEBUG = "debug"
CONF_POLLING_INTERVAL = "polling_interval"
CONF_POLLING_INTENSITY = "polling_intensity"

# How long to wait for the zwave network to be ready.
NETWORK_READY_WAIT_SECS = 30

SERVICE_ADD_NODE = "add_node"
SERVICE_REMOVE_NODE = "remove_node"
SERVICE_HEAL_NETWORK = "heal_network"
SERVICE_SOFT_RESET = "soft_reset"
SERVICE_TEST_NETWORK = "test_network"

DISCOVER_SENSORS = "zwave.sensors"
DISCOVER_SWITCHES = "zwave.switch"
DISCOVER_LIGHTS = "zwave.light"
DISCOVER_BINARY_SENSORS = 'zwave.binary_sensor'
DISCOVER_THERMOSTATS = 'zwave.thermostat'
DISCOVER_HVAC = 'zwave.hvac'
DISCOVER_LOCKS = 'zwave.lock'

EVENT_SCENE_ACTIVATED = "zwave.scene_activated"

COMMAND_CLASS_SWITCH_MULTILEVEL = 38
COMMAND_CLASS_DOOR_LOCK = 98
COMMAND_CLASS_SWITCH_BINARY = 37
COMMAND_CLASS_SENSOR_BINARY = 48
COMMAND_CLASS_SENSOR_MULTILEVEL = 49
COMMAND_CLASS_METER = 50
COMMAND_CLASS_BATTERY = 128
COMMAND_CLASS_ALARM = 113  # 0x71
COMMAND_CLASS_THERMOSTAT_SETPOINT = 67  # 0x43
COMMAND_CLASS_THERMOSTAT_FAN_MODE = 68  # 0x44

GENRE_WHATEVER = None
GENRE_USER = "User"

TYPE_WHATEVER = None
TYPE_BYTE = "Byte"
TYPE_BOOL = "Bool"
TYPE_DECIMAL = "Decimal"


# List of tuple (DOMAIN, discovered service, supported command classes,
# value type).
DISCOVERY_COMPONENTS = [
    ('sensor',
     DISCOVER_SENSORS,
     [COMMAND_CLASS_SENSOR_MULTILEVEL,
      COMMAND_CLASS_METER,
      COMMAND_CLASS_ALARM],
     TYPE_WHATEVER,
     GENRE_USER),
    ('light',
     DISCOVER_LIGHTS,
     [COMMAND_CLASS_SWITCH_MULTILEVEL],
     TYPE_BYTE,
     GENRE_USER),
    ('switch',
     DISCOVER_SWITCHES,
     [COMMAND_CLASS_SWITCH_BINARY],
     TYPE_BOOL,
     GENRE_USER),
    ('binary_sensor',
     DISCOVER_BINARY_SENSORS,
     [COMMAND_CLASS_SENSOR_BINARY],
     TYPE_BOOL,
     GENRE_USER),
    ('thermostat',
     DISCOVER_THERMOSTATS,
     [COMMAND_CLASS_THERMOSTAT_SETPOINT],
     TYPE_WHATEVER,
     GENRE_WHATEVER),
    ('hvac',
     DISCOVER_HVAC,
     [COMMAND_CLASS_THERMOSTAT_FAN_MODE],
     TYPE_WHATEVER,
     GENRE_WHATEVER),
    ('lock',
     DISCOVER_LOCKS,
     [COMMAND_CLASS_DOOR_LOCK],
     TYPE_BOOL,
     GENRE_USER),
]


ATTR_NODE_ID = "node_id"
ATTR_VALUE_ID = "value_id"

ATTR_SCENE_ID = "scene_id"

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
                                    ZWaveNetwork.SIGNAL_VALUE_ADDED):
                pprint(_obj_to_dict(value))

            print("")

        dispatcher.connect(log_all, weak=False)

    def value_added(node, value):
        """Called when a value is added to a node on the network."""
        for (component,
             discovery_service,
             command_ids,
             value_type,
             value_genre) in DISCOVERY_COMPONENTS:

            if value.command_class not in command_ids:
                continue
            if value_type is not None and value_type != value.type:
                continue
            if value_genre is not None and value_genre != value.genre:
                continue

            # Ensure component is loaded
            bootstrap.setup_component(hass, component, config)

            # Configure node
            name = "{}.{}".format(component, _object_id(value))

            node_config = customize.get(name, {})
            polling_intensity = convert(
                node_config.get(CONF_POLLING_INTENSITY), int)
            if polling_intensity:
                value.enable_poll(polling_intensity)
            else:
                value.disable_poll()

            # Fire discovery event
            hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
                ATTR_SERVICE: discovery_service,
                ATTR_DISCOVERED: {
                    ATTR_NODE_ID: node.node_id,
                    ATTR_VALUE_ID: value.value_id,
                }
            })

    def scene_activated(node, scene_id):
        """Called when a scene is activated on any node in the network."""
        name = _node_name(node)
        object_id = "{}_{}".format(slugify(name), node.node_id)

        hass.bus.fire(EVENT_SCENE_ACTIVATED, {
            ATTR_ENTITY_ID: object_id,
            ATTR_SCENE_ID: scene_id
        })

    dispatcher.connect(
        value_added, ZWaveNetwork.SIGNAL_VALUE_ADDED, weak=False)
    dispatcher.connect(
        scene_activated, ZWaveNetwork.SIGNAL_SCENE_EVENT, weak=False)

    def add_node(event):
        """Switch into inclusion mode."""
        NETWORK.controller.begin_command_add_device()

    def remove_node(event):
        """Switch into exclusion mode."""
        NETWORK.controller.begin_command_remove_device()

    def heal_network(event):
        """Heal the network."""
        NETWORK.heal()

    def soft_reset(event):
        """Soft reset the controller."""
        NETWORK.controller.soft_reset()

    def test_network(event):
        """Test the network by sending commands to all the nodes."""
        NETWORK.test()

    def stop_zwave(event):
        """Stop Z-Wave."""
        NETWORK.stop()

    def start_zwave(event):
        """Startup Z-Wave."""
        NETWORK.start()

        # Need to be in STATE_AWAKED before talking to nodes.
        # Wait up to NETWORK_READY_WAIT_SECS seconds for the zwave network
        # to be ready.
        for i in range(NETWORK_READY_WAIT_SECS):
            _LOGGER.info(
                "network state: %d %s", NETWORK.state, NETWORK.state_str)
            if NETWORK.state >= NETWORK.STATE_AWAKED:
                _LOGGER.info("zwave ready after %d seconds", i)
                break
            time.sleep(1)
        else:
            _LOGGER.warning(
                "zwave not ready after %d seconds, continuing anyway",
                NETWORK_READY_WAIT_SECS)
            _LOGGER.info(
                "final network state: %d %s", NETWORK.state, NETWORK.state_str)

        polling_interval = convert(
            config[DOMAIN].get(CONF_POLLING_INTERVAL), int)
        if polling_interval is not None:
            NETWORK.set_poll_interval(polling_interval, False)

        poll_interval = NETWORK.get_poll_interval()
        _LOGGER.info("zwave polling interval set to %d ms", poll_interval)

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_zwave)

        # Register add / remove node services for Z-Wave sticks without
        # hardware inclusion button
        hass.services.register(DOMAIN, SERVICE_ADD_NODE, add_node)
        hass.services.register(DOMAIN, SERVICE_REMOVE_NODE, remove_node)
        hass.services.register(DOMAIN, SERVICE_HEAL_NETWORK, heal_network)
        hass.services.register(DOMAIN, SERVICE_SOFT_RESET, soft_reset)
        hass.services.register(DOMAIN, SERVICE_TEST_NETWORK, test_network)

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
