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

DOMAIN = "zwave"
REQUIREMENTS = ['pydispatcher==2.0.5']

CONF_USB_STICK_PATH = "usb_path"
DEFAULT_CONF_USB_STICK_PATH = "/zwaveusbstick"
CONF_DEBUG = "debug"
CONF_POLLING_INTERVAL = "polling_interval"
CONF_POLLING_INTENSITY = "polling_intensity"
CONF_AUTOHEAL = "autoheal"
DEFAULT_CONF_AUTOHEAL = True

# How long to wait for the zwave network to be ready.
NETWORK_READY_WAIT_SECS = 30

SERVICE_ADD_NODE = "add_node"
SERVICE_ADD_NODE_SECURE = "add_node_secure"
SERVICE_REMOVE_NODE = "remove_node"
SERVICE_CANCEL_COMMAND = "cancel_command"
SERVICE_HEAL_NETWORK = "heal_network"
SERVICE_SOFT_RESET = "soft_reset"
SERVICE_TEST_NETWORK = "test_network"
SERVICE_STOP_NETWORK = "stop_network"
SERVICE_START_NETWORK = "start_network"
SERVICE_RENAME_NODE = "rename_node"

EVENT_SCENE_ACTIVATED = "zwave.scene_activated"
EVENT_NODE_EVENT = "zwave.node_event"
EVENT_NETWORK_READY = "zwave.network_ready"
EVENT_NETWORK_COMPLETE = "zwave.network_complete"
EVENT_NETWORK_START = "zwave.network_start"
EVENT_NETWORK_STOP = "zwave.network_stop"

COMMAND_CLASS_ALARM = 113
COMMAND_CLASS_ANTITHEFT = 93
COMMAND_CLASS_APPLICATION_CAPABILITY = 87
COMMAND_CLASS_APPLICATION_STATUS = 34
COMMAND_CLASS_ASSOCIATION = 133
COMMAND_CLASS_ASSOCIATION_COMMAND_CONFIGURATION = 155
COMMAND_CLASS_ASSOCIATION_GRP_INFO = 89
COMMAND_CLASS_BARRIER_OPERATOR = 102
COMMAND_CLASS_BASIC = 32
COMMAND_CLASS_BASIC_TARIFF_INFO = 54
COMMAND_CLASS_BASIC_WINDOW_COVERING = 80
COMMAND_CLASS_BATTERY = 128
COMMAND_CLASS_CENTRAL_SCENE = 91
COMMAND_CLASS_CLIMATE_CONTROL_SCHEDULE = 70
COMMAND_CLASS_CLOCK = 129
COMMAND_CLASS_CONFIGURATION = 112
COMMAND_CLASS_CONTROLLER_REPLICATION = 33
COMMAND_CLASS_CRC_16_ENCAP = 86
COMMAND_CLASS_DCP_CONFIG = 58
COMMAND_CLASS_DCP_MONITOR = 59
COMMAND_CLASS_DEVICE_RESET_LOCALLY = 90
COMMAND_CLASS_DOOR_LOCK = 98
COMMAND_CLASS_DOOR_LOCK_LOGGING = 76
COMMAND_CLASS_ENERGY_PRODUCTION = 144
COMMAND_CLASS_ENTRY_CONTROL = 111
COMMAND_CLASS_FIRMWARE_UPDATE_MD = 122
COMMAND_CLASS_GEOGRAPHIC_LOCATION = 140
COMMAND_CLASS_GROUPING_NAME = 123
COMMAND_CLASS_HAIL = 130
COMMAND_CLASS_HRV_CONTROL = 57
COMMAND_CLASS_HRV_STATUS = 55
COMMAND_CLASS_HUMIDITY_CONTROL_MODE = 109
COMMAND_CLASS_HUMIDITY_CONTROL_OPERATING_STATE = 110
COMMAND_CLASS_HUMIDITY_CONTROL_SETPOINT = 100
COMMAND_CLASS_INDICATOR = 135
COMMAND_CLASS_IP_ASSOCIATION = 92
COMMAND_CLASS_IP_CONFIGURATION = 14
COMMAND_CLASS_IRRIGATION = 107
COMMAND_CLASS_LANGUAGE = 137
COMMAND_CLASS_LOCK = 118
COMMAND_CLASS_MAILBOX = 105
COMMAND_CLASS_MANUFACTURER_PROPRIETARY = 145
COMMAND_CLASS_MANUFACTURER_SPECIFIC = 114
COMMAND_CLASS_MARK = 239
COMMAND_CLASS_METER = 50
COMMAND_CLASS_METER_PULSE = 53
COMMAND_CLASS_METER_TBL_CONFIG = 60
COMMAND_CLASS_METER_TBL_MONITOR = 61
COMMAND_CLASS_METER_TBL_PUSH = 62
COMMAND_CLASS_MTP_WINDOW_COVERING = 81
COMMAND_CLASS_MULTI_CHANNEL = 96
COMMAND_CLASS_MULTI_CHANNEL_ASSOCIATION = 142
COMMAND_CLASS_MULTI_COMMAND = 143
COMMAND_CLASS_NETWORK_MANAGEMENT_BASIC = 77
COMMAND_CLASS_NETWORK_MANAGEMENT_INCLUSION = 52
COMMAND_CLASS_NETWORK_MANAGEMENT_PRIMARY = 84
COMMAND_CLASS_NETWORK_MANAGEMENT_PROXY = 82
COMMAND_CLASS_NO_OPERATION = 0
COMMAND_CLASS_NODE_NAMING = 119
COMMAND_CLASS_NON_INTEROPERABLE = 240
COMMAND_CLASS_NOTIFICATION = 113
COMMAND_CLASS_POWERLEVEL = 115
COMMAND_CLASS_PREPAYMENT = 63
COMMAND_CLASS_PREPAYMENT_ENCAPSULATION = 65
COMMAND_CLASS_PROPRIETARY = 136
COMMAND_CLASS_PROTECTION = 117
COMMAND_CLASS_RATE_TBL_CONFIG = 72
COMMAND_CLASS_RATE_TBL_MONITOR = 73
COMMAND_CLASS_REMOTE_ASSOCIATION_ACTIVATE = 124
COMMAND_CLASS_REMOTE_ASSOCIATION = 125
COMMAND_CLASS_SCENE_ACTIVATION = 43
COMMAND_CLASS_SCENE_ACTUATOR_CONF = 44
COMMAND_CLASS_SCENE_CONTROLLER_CONF = 45
COMMAND_CLASS_SCHEDULE = 83
COMMAND_CLASS_SCHEDULE_ENTRY_LOCK = 78
COMMAND_CLASS_SCREEN_ATTRIBUTES = 147
COMMAND_CLASS_SCREEN_MD = 146
COMMAND_CLASS_SECURITY = 152
COMMAND_CLASS_SECURITY_SCHEME0_MARK = 61696
COMMAND_CLASS_SENSOR_ALARM = 156
COMMAND_CLASS_SENSOR_BINARY = 48
COMMAND_CLASS_SENSOR_CONFIGURATION = 158
COMMAND_CLASS_SENSOR_MULTILEVEL = 49
COMMAND_CLASS_SILENCE_ALARM = 157
COMMAND_CLASS_SIMPLE_AV_CONTROL = 148
COMMAND_CLASS_SUPERVISION = 108
COMMAND_CLASS_SWITCH_ALL = 39
COMMAND_CLASS_SWITCH_BINARY = 37
COMMAND_CLASS_SWITCH_COLOR = 51
COMMAND_CLASS_SWITCH_MULTILEVEL = 38
COMMAND_CLASS_SWITCH_TOGGLE_BINARY = 40
COMMAND_CLASS_SWITCH_TOGGLE_MULTILEVEL = 41
COMMAND_CLASS_TARIFF_TBL_CONFIG = 74
COMMAND_CLASS_TARIFF_TBL_MONITOR = 75
COMMAND_CLASS_THERMOSTAT_FAN_MODE = 68
COMMAND_CLASS_THERMOSTAT_FAN_STATE = 69
COMMAND_CLASS_THERMOSTAT_MODE = 64
COMMAND_CLASS_THERMOSTAT_OPERATING_STATE = 66
COMMAND_CLASS_THERMOSTAT_SETBACK = 71
COMMAND_CLASS_THERMOSTAT_SETPOINT = 67
COMMAND_CLASS_TIME = 138
COMMAND_CLASS_TIME_PARAMETERS = 139
COMMAND_CLASS_TRANSPORT_SERVICE = 85
COMMAND_CLASS_USER_CODE = 99
COMMAND_CLASS_VERSION = 134
COMMAND_CLASS_WAKE_UP = 132
COMMAND_CLASS_ZIP = 35
COMMAND_CLASS_ZIP_NAMING = 104
COMMAND_CLASS_ZIP_ND = 88
COMMAND_CLASS_ZIP_6LOWPAN = 79
COMMAND_CLASS_ZIP_GATEWAY = 95
COMMAND_CLASS_ZIP_PORTAL = 97
COMMAND_CLASS_ZWAVEPLUS_INFO = 94
COMMAND_CLASS_WHATEVER = None  # Match ALL
COMMAND_CLASS_WINDOW_COVERING = 106

GENERIC_TYPE_WHATEVER = None  # Match ALL
SPECIFIC_TYPE_WHATEVER = None  # Match ALL
SPECIFIC_TYPE_NOT_USED = 0  # Available in all Generic types

GENERIC_TYPE_AV_CONTROL_POINT = 3
SPECIFIC_TYPE_DOORBELL = 18
SPECIFIC_TYPE_SATELLITE_RECIEVER = 4
SPECIFIC_TYPE_SATELLITE_RECIEVER_V2 = 17

GENERIC_TYPE_DISPLAY = 4
SPECIFIC_TYPE_SIMPLE_DISPLAY = 1

GENERIC_TYPE_ENTRY_CONTROL = 64
SPECIFIC_TYPE_DOOR_LOCK = 1
SPECIFIC_TYPE_ADVANCED_DOOR_LOCK = 2
SPECIFIC_TYPE_SECURE_KEYPAD_DOOR_LOCK = 3
SPECIFIC_TYPE_SECURE_KEYPAD_DOOR_LOCK_DEADBOLT = 4
SPECIFIC_TYPE_SECURE_DOOR = 5
SPECIFIC_TYPE_SECURE_GATE = 6
SPECIFIC_TYPE_SECURE_BARRIER_ADDON = 7
SPECIFIC_TYPE_SECURE_BARRIER_OPEN_ONLY = 8
SPECIFIC_TYPE_SECURE_BARRIER_CLOSE_ONLY = 9
SPECIFIC_TYPE_SECURE_LOCKBOX = 10
SPECIFIC_TYPE_SECURE_KEYPAD = 11

GENERIC_TYPE_GENERIC_CONTROLLER = 1
SPECIFIC_TYPE_PORTABLE_CONTROLLER = 1
SPECIFIC_TYPE_PORTABLE_SCENE_CONTROLLER = 2
SPECIFIC_TYPE_PORTABLE_INSTALLER_TOOL = 3
SPECIFIC_TYPE_REMOTE_CONTROL_AV = 4
SPECIFIC_TYPE_REMOTE_CONTROL_SIMPLE = 6

GENERIC_TYPE_METER = 49
SPECIFIC_TYPE_SIMPLE_METER = 1
SPECIFIC_TYPE_ADV_ENERGY_CONTROL = 2
SPECIFIC_TYPE_WHOLE_HOME_METER_SIMPLE = 3

GENERIC_TYPE_METER_PULSE = 48

GENERIC_TYPE_NON_INTEROPERABLE = 255

GENERIC_TYPE_REPEATER_SLAVE = 15
SPECIFIC_TYPE_REPEATER_SLAVE = 1
SPECIFIC_TYPE_VIRTUAL_NODE = 2

GENERIC_TYPE_SECURITY_PANEL = 23
SPECIFIC_TYPE_ZONED_SECURITY_PANEL = 1

GENERIC_TYPE_SEMI_INTEROPERABLE = 80
SPECIFIC_TYPE_ENERGY_PRODUCTION = 1

GENERIC_TYPE_SENSOR_ALARM = 161
SPECIFIC_TYPE_ADV_ZENSOR_NET_ALARM_SENSOR = 5
SPECIFIC_TYPE_ADV_ZENSOR_NET_SMOKE_SENSOR = 10
SPECIFIC_TYPE_BASIC_ROUTING_ALARM_SENSOR = 1
SPECIFIC_TYPE_BASIC_ROUTING_SMOKE_SENSOR = 6
SPECIFIC_TYPE_BASIC_ZENSOR_NET_ALARM_SENSOR = 3
SPECIFIC_TYPE_BASIC_ZENSOR_NET_SMOKE_SENSOR = 8
SPECIFIC_TYPE_ROUTING_ALARM_SENSOR = 2
SPECIFIC_TYPE_ROUTING_SMOKE_SENSOR = 7
SPECIFIC_TYPE_ZENSOR_NET_ALARM_SENSOR = 4
SPECIFIC_TYPE_ZENSOR_NET_SMOKE_SENSOR = 9
SPECIFIC_TYPE_ALARM_SENSOR = 11

GENERIC_TYPE_SENSOR_BINARY = 32
SPECIFIC_TYPE_ROUTING_SENSOR_BINARY = 1

GENERIC_TYPE_SENSOR_MULTILEVEL = 33
SPECIFIC_TYPE_ROUTING_SENSOR_MULTILEVEL = 1
SPECIFIC_TYPE_CHIMNEY_FAN = 2

GENERIC_TYPE_STATIC_CONTROLLER = 2
SPECIFIC_TYPE_PC_CONTROLLER = 1
SPECIFIC_TYPE_SCENE_CONTROLLER = 2
SPECIFIC_TYPE_STATIC_INSTALLER_TOOL = 3
SPECIFIC_TYPE_SET_TOP_BOX = 4
SPECIFIC_TYPE_SUB_SYSTEM_CONTROLLER = 5
SPECIFIC_TYPE_TV = 6
SPECIFIC_TYPE_GATEWAY = 7

GENERIC_TYPE_SWITCH_BINARY = 16
SPECIFIC_TYPE_POWER_SWITCH_BINARY = 1
SPECIFIC_TYPE_SCENE_SWITCH_BINARY = 3
SPECIFIC_TYPE_POWER_STRIP = 4
SPECIFIC_TYPE_SIREN = 5
SPECIFIC_TYPE_VALVE_OPEN_CLOSE = 6
SPECIFIC_TYPE_COLOR_TUNABLE_BINARY = 2
SPECIFIC_TYPE_IRRIGATION_CONTROLLER = 7

GENERIC_TYPE_SWITCH_MULTILEVEL = 17
SPECIFIC_TYPE_CLASS_A_MOTOR_CONTROL = 5
SPECIFIC_TYPE_CLASS_B_MOTOR_CONTROL = 6
SPECIFIC_TYPE_CLASS_C_MOTOR_CONTROL = 7
SPECIFIC_TYPE_MOTOR_MULTIPOSITION = 3
SPECIFIC_TYPE_POWER_SWITCH_MULTILEVEL = 1
SPECIFIC_TYPE_SCENE_SWITCH_MULTILEVEL = 4
SPECIFIC_TYPE_FAN_SWITCH = 8
SPECIFIC_TYPE_COLOR_TUNABLE_MULTILEVEL = 2

GENERIC_TYPE_SWITCH_REMOTE = 18
SPECIFIC_TYPE_REMOTE_BINARY = 1
SPECIFIC_TYPE_REMOTE_MULTILEVEL = 2
SPECIFIC_TYPE_REMOTE_TOGGLE_BINARY = 3
SPECIFIC_TYPE_REMOTE_TOGGLE_MULTILEVEL = 4

GENERIC_TYPE_SWITCH_TOGGLE = 19
SPECIFIC_TYPE_SWITCH_TOGGLE_BINARY = 1
SPECIFIC_TYPE_SWITCH_TOGGLE_MULTILEVEL = 2

GENERIC_TYPE_THERMOSTAT = 8
SPECIFIC_TYPE_SETBACK_SCHEDULE_THERMOSTAT = 3
SPECIFIC_TYPE_SETBACK_THERMOSTAT = 5
SPECIFIC_TYPE_SETPOINT_THERMOSTAT = 4
SPECIFIC_TYPE_THERMOSTAT_GENERAL = 2
SPECIFIC_TYPE_THERMOSTAT_GENERAL_V2 = 6
SPECIFIC_TYPE_THERMOSTAT_HEATING = 1

GENERIC_TYPE_VENTILATION = 22
SPECIFIC_TYPE_RESIDENTIAL_HRV = 1

GENERIC_TYPE_WINDOWS_COVERING = 9
SPECIFIC_TYPE_SIMPLE_WINDOW_COVERING = 1

GENERIC_TYPE_ZIP_NODE = 21
SPECIFIC_TYPE_ZIP_ADV_NODE = 2
SPECIFIC_TYPE_ZIP_TUN_NODE = 1

GENERIC_TYPE_WALL_CONTROLLER = 24
SPECIFIC_TYPE_BASIC_WALL_CONTROLLER = 1

GENERIC_TYPE_NETWORK_EXTENDER = 5
SPECIFIC_TYPE_SECURE_EXTENDER = 1

GENERIC_TYPE_APPLIANCE = 6
SPECIFIC_TYPE_GENERAL_APPLIANCE = 1
SPECIFIC_TYPE_KITCHEN_APPLIANCE = 2
SPECIFIC_TYPE_LAUNDRY_APPLIANCE = 3

GENERIC_TYPE_SENSOR_NOTIFICATION = 7
SPECIFIC_TYPE_NOTIFICATION_SENSOR = 1

GENRE_WHATEVER = None
GENRE_USER = "User"

TYPE_WHATEVER = None
TYPE_BYTE = "Byte"
TYPE_BOOL = "Bool"
TYPE_DECIMAL = "Decimal"


# List of tuple (DOMAIN, discovered service, supported command classes,
# value type, genre type, specific device class).
DISCOVERY_COMPONENTS = [
    ('sensor',
     [GENERIC_TYPE_WHATEVER],
     [SPECIFIC_TYPE_WHATEVER],
     [COMMAND_CLASS_SENSOR_MULTILEVEL,
      COMMAND_CLASS_METER,
      COMMAND_CLASS_ALARM,
      COMMAND_CLASS_SENSOR_ALARM],
     TYPE_WHATEVER,
     GENRE_USER),
    ('light',
     [GENERIC_TYPE_SWITCH_MULTILEVEL,
      GENERIC_TYPE_SWITCH_REMOTE],
     [SPECIFIC_TYPE_POWER_SWITCH_MULTILEVEL,
      SPECIFIC_TYPE_SCENE_SWITCH_MULTILEVEL,
      SPECIFIC_TYPE_NOT_USED],
     [COMMAND_CLASS_SWITCH_MULTILEVEL],
     TYPE_BYTE,
     GENRE_USER),
    ('switch',
     [GENERIC_TYPE_SENSOR_ALARM,
      GENERIC_TYPE_SENSOR_BINARY,
      GENERIC_TYPE_SWITCH_BINARY,
      GENERIC_TYPE_ENTRY_CONTROL,
      GENERIC_TYPE_SENSOR_MULTILEVEL,
      GENERIC_TYPE_SWITCH_MULTILEVEL,
      GENERIC_TYPE_SENSOR_NOTIFICATION,
      GENERIC_TYPE_GENERIC_CONTROLLER,
      GENERIC_TYPE_SWITCH_REMOTE,
      GENERIC_TYPE_REPEATER_SLAVE,
      GENERIC_TYPE_THERMOSTAT,
      GENERIC_TYPE_WALL_CONTROLLER],
     [SPECIFIC_TYPE_WHATEVER],
     [COMMAND_CLASS_SWITCH_BINARY],
     TYPE_BOOL,
     GENRE_USER),
    ('binary_sensor',
     [GENERIC_TYPE_SENSOR_ALARM,
      GENERIC_TYPE_SENSOR_BINARY,
      GENERIC_TYPE_SWITCH_BINARY,
      GENERIC_TYPE_METER,
      GENERIC_TYPE_SENSOR_MULTILEVEL,
      GENERIC_TYPE_SWITCH_MULTILEVEL,
      GENERIC_TYPE_SENSOR_NOTIFICATION,
      GENERIC_TYPE_THERMOSTAT],
     [SPECIFIC_TYPE_WHATEVER],
     [COMMAND_CLASS_SENSOR_BINARY],
     TYPE_BOOL,
     GENRE_USER),
    ('lock',
     [GENERIC_TYPE_ENTRY_CONTROL],
     [SPECIFIC_TYPE_ADVANCED_DOOR_LOCK,
      SPECIFIC_TYPE_SECURE_KEYPAD_DOOR_LOCK],
     [COMMAND_CLASS_DOOR_LOCK],
     TYPE_BOOL,
     GENRE_USER),
    ('cover',
     [GENERIC_TYPE_SWITCH_MULTILEVEL,
      GENERIC_TYPE_ENTRY_CONTROL],
     [SPECIFIC_TYPE_CLASS_A_MOTOR_CONTROL,
      SPECIFIC_TYPE_CLASS_B_MOTOR_CONTROL,
      SPECIFIC_TYPE_CLASS_C_MOTOR_CONTROL,
      SPECIFIC_TYPE_MOTOR_MULTIPOSITION,
      SPECIFIC_TYPE_SECURE_BARRIER_ADDON,
      SPECIFIC_TYPE_SECURE_DOOR],
     [COMMAND_CLASS_SWITCH_BINARY,
      COMMAND_CLASS_BARRIER_OPERATOR,
      COMMAND_CLASS_SWITCH_MULTILEVEL],
     TYPE_WHATEVER,
     GENRE_USER),
    ('climate',
     [GENERIC_TYPE_THERMOSTAT],
     [SPECIFIC_TYPE_WHATEVER],
     [COMMAND_CLASS_THERMOSTAT_SETPOINT],
     TYPE_WHATEVER,
     GENRE_WHATEVER),
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
        hass.bus.fire(EVENT_SCENE_ACTIVATED, {
            ATTR_ENTITY_ID: _node_object_id(node),
            ATTR_OBJECT_ID: _node_object_id(node),
            ATTR_SCENE_ID: scene_id
        })

    def node_event_activated(node, value):
        """Called when a nodeevent is activated on any node in the network."""
        hass.bus.fire(EVENT_NODE_EVENT, {
            ATTR_OBJECT_ID: _node_object_id(node),
            ATTR_BASIC_LEVEL: value
        })

    def network_ready():
        """Called when all awake nodes have been queried."""
        _LOGGER.info("Zwave network is ready for use. All awake nodes"
                     " have been queried. Sleeping nodes will be"
                     " queried when they awake.")
        hass.bus.fire(EVENT_NETWORK_READY)

    def network_complete():
        """Called when all nodes on network have been queried."""
        _LOGGER.info("Zwave network is complete. All nodes on the network"
                     " have been queried")
        hass.bus.fire(EVENT_NETWORK_COMPLETE)

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
        hass.bus.fire(EVENT_NETWORK_STOP)

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
        hass.bus.fire(EVENT_NETWORK_START)

        # Need to be in STATE_AWAKED before talking to nodes.
        # Wait up to NETWORK_READY_WAIT_SECS seconds for the zwave network
        # to be ready.
        for i in range(NETWORK_READY_WAIT_SECS):
            _LOGGER.debug(
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

        # Register node services for Z-Wave network
        hass.services.register(DOMAIN, SERVICE_ADD_NODE, add_node)
        hass.services.register(DOMAIN, SERVICE_ADD_NODE_SECURE,
                               add_node_secure)
        hass.services.register(DOMAIN, SERVICE_REMOVE_NODE, remove_node)
        hass.services.register(DOMAIN, SERVICE_CANCEL_COMMAND, cancel_command)
        hass.services.register(DOMAIN, SERVICE_HEAL_NETWORK, heal_network)
        hass.services.register(DOMAIN, SERVICE_SOFT_RESET, soft_reset)
        hass.services.register(DOMAIN, SERVICE_TEST_NETWORK, test_network)
        hass.services.register(DOMAIN, SERVICE_STOP_NETWORK, stop_zwave)
        hass.services.register(DOMAIN, SERVICE_START_NETWORK, start_zwave)
        hass.services.register(DOMAIN, SERVICE_RENAME_NODE, rename_node,
                               descriptions[DOMAIN][SERVICE_RENAME_NODE],
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
