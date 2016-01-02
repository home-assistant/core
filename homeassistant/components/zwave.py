"""
homeassistant.components.zwave
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Connects Home Assistant to a Z-Wave network.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zwave/
"""
import sys
import os.path

from pprint import pprint

from homeassistant import bootstrap
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    EVENT_PLATFORM_DISCOVERED, ATTR_SERVICE, ATTR_DISCOVERED)

DOMAIN = "zwave"
REQUIREMENTS = ['pydispatcher==2.0.5']

CONF_USB_STICK_PATH = "usb_path"
DEFAULT_CONF_USB_STICK_PATH = "/zwaveusbstick"
CONF_DEBUG = "debug"
CONF_POLLING_INTERVAL = "polling_interval"
DEFAULT_ZWAVE_CONFIG_PATH = os.path.join(sys.prefix, 'share',
                                         'python-openzwave', 'config')

DISCOVER_SENSORS = "zwave.sensors"
DISCOVER_SWITCHES = "zwave.switch"
DISCOVER_LIGHTS = "zwave.light"

COMMAND_CLASS_SWITCH_MULTILEVEL = 38

COMMAND_CLASS_SWITCH_BINARY = 37
COMMAND_CLASS_SENSOR_BINARY = 48
COMMAND_CLASS_SENSOR_MULTILEVEL = 49
COMMAND_CLASS_METER = 50
COMMAND_CLASS_BATTERY = 128

GENRE_WHATEVER = None
GENRE_USER = "User"

TYPE_WHATEVER = None
TYPE_BYTE = "Byte"
TYPE_BOOL = "Bool"
TYPE_DECIMAL = "Decimal"

# list of tuple (DOMAIN, discovered service, supported command
# classes, value type)
DISCOVERY_COMPONENTS = [
    ('sensor',
     DISCOVER_SENSORS,
     [COMMAND_CLASS_SENSOR_BINARY,
      COMMAND_CLASS_SENSOR_MULTILEVEL,
      COMMAND_CLASS_METER],
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
]

ATTR_NODE_ID = "node_id"
ATTR_VALUE_ID = "value_id"

NETWORK = None


def _obj_to_dict(obj):
    """ Converts an obj into a hash for debug. """
    return {key: getattr(obj, key) for key
            in dir(obj)
            if key[0] != '_' and not hasattr(getattr(obj, key), '__call__')}


def nice_print_node(node):
    """ Prints a nice formatted node to the output (debug method). """
    node_dict = _obj_to_dict(node)
    node_dict['values'] = {value_id: _obj_to_dict(value)
                           for value_id, value in node.values.items()}

    print("\n\n\n")
    print("FOUND NODE", node.product_name)
    pprint(node_dict)
    print("\n\n\n")


def get_config_value(node, value_index):
    """ Returns the current config value for a specific index. """

    try:
        for value in node.values.values():
            # 112 == config command class
            if value.command_class == 112 and value.index == value_index:
                return value.data
    except RuntimeError:
        # If we get an runtime error the dict has changed while
        # we was looking for a value, just do it again
        return get_config_value(node, value_index)


def setup(hass, config):
    """
    Setup Z-wave.
    Will automatically load components to support devices found on the network.
    """
    # pylint: disable=global-statement, import-error
    global NETWORK

    from pydispatch import dispatcher
    from openzwave.option import ZWaveOption
    from openzwave.network import ZWaveNetwork

    use_debug = str(config[DOMAIN].get(CONF_DEBUG)) == '1'

    # Setup options
    options = ZWaveOption(
        config[DOMAIN].get(CONF_USB_STICK_PATH, DEFAULT_CONF_USB_STICK_PATH),
        user_path=hass.config.config_dir,
        config_path=config[DOMAIN].get('config_path',
                                       DEFAULT_ZWAVE_CONFIG_PATH),)

    options.set_console_output(use_debug)
    options.lock()

    NETWORK = ZWaveNetwork(options, autostart=False)

    if use_debug:
        def log_all(signal, value=None):
            """ Log all the signals. """
            print("")
            print("SIGNAL *****", signal)
            if value and signal in (ZWaveNetwork.SIGNAL_VALUE_CHANGED,
                                    ZWaveNetwork.SIGNAL_VALUE_ADDED):
                pprint(_obj_to_dict(value))
            print("")

        dispatcher.connect(log_all, weak=False)

    def value_added(node, value):
        """ Called when a value is added to a node on the network. """

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

            # Fire discovery event
            hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
                ATTR_SERVICE: discovery_service,
                ATTR_DISCOVERED: {
                    ATTR_NODE_ID: node.node_id,
                    ATTR_VALUE_ID: value.value_id,
                }
            })

    dispatcher.connect(
        value_added, ZWaveNetwork.SIGNAL_VALUE_ADDED, weak=False)

    def stop_zwave(event):
        """ Stop Z-wave. """
        NETWORK.stop()

    def start_zwave(event):
        """ Called when Home Assistant starts up. """
        NETWORK.start()

        polling_interval = config[DOMAIN].get(CONF_POLLING_INTERVAL, None)
        if polling_interval is not None:
            NETWORK.setPollInterval(polling_interval)

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_zwave)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_zwave)

    return True
