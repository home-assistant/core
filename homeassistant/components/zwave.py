"""
homeassistant.components.zwave
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Connects Home Assistant to a Z-Wave network.
"""
from pprint import pprint

from homeassistant import bootstrap
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    EVENT_PLATFORM_DISCOVERED, ATTR_SERVICE, ATTR_DISCOVERED)

DOMAIN = "zwave"
DEPENDENCIES = []
REQUIREMENTS = ['pydispatcher==2.0.5']

CONF_USB_STICK_PATH = "usb_path"
DEFAULT_CONF_USB_STICK_PATH = "/zwaveusbstick"
CONF_DEBUG = "debug"

DISCOVER_SENSORS = "zwave.sensors"

COMMAND_CLASS_SENSOR_BINARY = 48
COMMAND_CLASS_SENSOR_MULTILEVEL = 49
COMMAND_CLASS_BATTERY = 128

# list of tuple (DOMAIN, discovered service, supported command classes)
DISCOVERY_COMPONENTS = [
    ('sensor', DISCOVER_SENSORS,
     [COMMAND_CLASS_SENSOR_BINARY, COMMAND_CLASS_SENSOR_MULTILEVEL]),
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
    """ Prints a nice formatted node to the output (debug method) """
    node_dict = _obj_to_dict(node)
    node_dict['values'] = {value_id: _obj_to_dict(value)
                           for value_id, value in node.values.items()}

    print("\n\n\n")
    print("FOUND NODE", node.product_name)
    pprint(node_dict)
    print("\n\n\n")


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
        user_path=hass.config.config_dir)

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
        for component, discovery_service, command_ids in DISCOVERY_COMPONENTS:
            if value.command_class in command_ids:
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

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_zwave)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_zwave)

    return True
