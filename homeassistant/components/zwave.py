from homeassistant import bootstrap
from homeassistant.loader import get_component
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    EVENT_PLATFORM_DISCOVERED, ATTR_SERVICE, ATTR_DISCOVERED)

DOMAIN = "zwave"
DEPENDENCIES = []

CONF_USB_STICK_PATH = "usb_path"
DEFAULT_CONF_USB_STICK_PATH = "/zwaveusbstick"
CONF_DEBUG = "debug"

DISCOVER_SENSORS = "zwave.sensors"

VALUE_SENSOR = 72057594076463104
VALUE_TEMPERATURE = 72057594076479506
VALUE_LUMINANCE = 72057594076479538
VALUE_RELATIVE_HUMIDITY = 72057594076479570
VALUE_BATTERY_LEVEL = 72057594077773825

NETWORK = None


def get_node_value(node, key):
    """ Helper function to get a node value. """
    return node.values[key].data if key in node.values else None


def nice_print_node(node):
    """ Prints a nice formatted node to the output """
    from pprint import pprint

    print("")
    print("")
    print("")
    print("FOUND NODE", node.product_name)
    pprint({key: getattr(node, key) for key
            in dir(node)
            if key != 'values' and
            not hasattr(getattr(node, key), '__call__')})
    print("")
    print("")
    print("VALUES")
    pprint({
        value_id: {key: getattr(value, key) for key
                   in dir(value)
                   if key[0] != '_' and
                   not hasattr(getattr(value, key), '__call__')}
        for value_id, value in node.values.items()})

    print("")
    print("")


def setup(hass, config):
    """
    Setup Z-wave.
    Will automatically load components to support devices found on the network.
    """
    global NETWORK

    from louie import connect
    from openzwave.option import ZWaveOption
    from openzwave.network import ZWaveNetwork

    use_debug = config[DOMAIN].get(CONF_DEBUG) == '1'

    # Setup options
    options = ZWaveOption(
        config[DOMAIN].get(CONF_USB_STICK_PATH, DEFAULT_CONF_USB_STICK_PATH),
        user_path=hass.config_dir)

    options.set_associate(True)
    options.set_console_output(use_debug)
    options.lock()

    NETWORK = ZWaveNetwork(options, autostart=False)

    if use_debug:
        def log_all(signal):
            print("")
            print("LOUIE SIGNAL *****", signal)
            print("")

        connect(log_all, weak=False)

    def zwave_init_done(network):
        """ Called when Z-Wave has initialized. """
        init_sensor = False

        # This should be rewritten more efficient when supporting more types
        for node in network.nodes.values():
            if use_debug:
                nice_print_node(node)

            if get_node_value(node, VALUE_SENSOR) and not init_sensor:
                init_sensor = True

                component = get_component('sensor')

                # Ensure component is loaded
                if component.DOMAIN not in hass.components:
                    bootstrap.setup_component(hass, component.DOMAIN, config)

                # Fire discovery event
                hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
                    ATTR_SERVICE: DISCOVER_SENSORS,
                    ATTR_DISCOVERED: {}
                })

    connect(
        zwave_init_done, ZWaveNetwork.SIGNAL_NETWORK_READY, weak=False)

    def stop_zwave(event):
        """ Stop Z-wave. """
        NETWORK.stop()

    def start_zwave(event):
        """ Called when Home Assistant starts up. """
        NETWORK.start()

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_zwave)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_zwave)
