"""
homeassistant.components.mysensors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
MySensors component that connects to a MySensors gateway via pymysensors
API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mysensors.html


New features:

New MySensors component.
Updated MySensors Sensor platform.
New MySensors Switch platform.
Multiple gateways are now supported.

Configuration.yaml:

mysensors:
  gateways:
    - port: '/dev/ttyUSB0'
      persistence_file: 'path/mysensors.json'
    - port: '/dev/ttyACM1'
      persistence_file: 'path/mysensors2.json'
  debug: true
  persistence: true
  version: '1.5'
"""
import logging

from homeassistant.helpers import validate_config
import homeassistant.bootstrap as bootstrap

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    TEMP_CELCIUS,
    CONF_PLATFORM)

CONF_GATEWAYS = 'gateways'
CONF_PORT = 'port'
CONF_DEBUG = 'debug'
CONF_PERSISTENCE = 'persistence'
CONF_PERSISTENCE_FILE = 'persistence_file'
CONF_VERSION = 'version'
DEFAULT_VERSION = '1.4'
VERSION = None

DOMAIN = 'mysensors'
DEPENDENCIES = []
REQUIREMENTS = [
    'https://github.com/theolind/pymysensors/archive/'
    '2aa8f32908e8c5bb3e5c77c5851db778f8635792.zip#pymysensors==0.3']
_LOGGER = logging.getLogger(__name__)
ATTR_NODE_ID = 'node_id'
ATTR_CHILD_ID = 'child_id'

COMPONENTS_WITH_MYSENSORS_PLATFORM = [
    'sensor',
    'switch',
]

IS_METRIC = None
CONST = None
GATEWAYS = None


def setup(hass, config):
    """Setup the MySensors component."""
    # pylint: disable=too-many-locals
    import mysensors.mysensors as mysensors

    if not validate_config(config,
                           {DOMAIN: [CONF_GATEWAYS]},
                           _LOGGER):
        return False

    global VERSION
    VERSION = config[DOMAIN].get(CONF_VERSION, DEFAULT_VERSION)

    global CONST
    if VERSION == '1.5':
        import mysensors.const_15 as const
        CONST = const
    else:
        import mysensors.const_14 as const
        CONST = const

    # Just assume celcius means that the user wants metric for now.
    # It may make more sense to make this a global config option in the future.
    global IS_METRIC
    IS_METRIC = (hass.config.temperature_unit == TEMP_CELCIUS)

    # Setup mysensors platforms
    mysensors_config = config.copy()
    for component in COMPONENTS_WITH_MYSENSORS_PLATFORM:
        mysensors_config[component] = {CONF_PLATFORM: 'mysensors'}
        if not bootstrap.setup_component(hass, component, mysensors_config):
            return False

    import homeassistant.components.sensor.mysensors as mysensors_sensor
    import homeassistant.components.switch.mysensors as mysensors_switch

    def callback_factory(gateway, port, devices):
        """Return a new callback function. Run once per gateway setup."""
        def node_update(update_type, nid):
            """Callback for node updates from the MySensors gateway."""
            _LOGGER.info('update %s: node %s', update_type, nid)

            mysensors_sensor.sensor_update(gateway, port, devices, nid)
            mysensors_switch.sensor_update(gateway, port, devices, nid)

        return node_update

    def setup_gateway(port, persistence, persistence_file):
        """Return gateway after setup of the gateway."""
        devices = {}    # keep track of devices added to HA
        gateway = mysensors.SerialGateway(port,
                                          persistence=persistence,
                                          persistence_file=persistence_file,
                                          protocol_version=VERSION)
        gateway.event_callback = callback_factory(gateway, port, devices)
        gateway.metric = IS_METRIC
        gateway.debug = config[DOMAIN].get(CONF_DEBUG, False)
        gateway.start()

        def persistence_update(event):
            """Callback to trigger update from persistence file."""
            for nid in gateway.sensors:
                gateway.event_callback('persistence', nid)

        if persistence:
            hass.bus.listen_once(
                EVENT_HOMEASSISTANT_START, persistence_update)

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                             lambda event: gateway.stop())

        return gateway

    # Setup all ports from config
    global GATEWAYS
    GATEWAYS = {}
    conf_gateways = config[DOMAIN][CONF_GATEWAYS]
    if isinstance(conf_gateways, dict):
        conf_gateways = [conf_gateways]
    persistence = config[DOMAIN].get(CONF_PERSISTENCE, True)
    for index, gway in enumerate(conf_gateways):
        port = gway[CONF_PORT]
        persistence_file = gway.get(
            CONF_PERSISTENCE_FILE,
            hass.config.path('mysensors{}.pickle'.format(index + 1)))
        GATEWAYS[port] = setup_gateway(
            port, persistence, persistence_file)

    return True


def mysensors_update(platform_type):
    """Decorator for callback function for mysensor updates."""
    def wrapper(gateway, port, devices, nid):
        """Wrapper function in the decorator."""
        if gateway.sensors[nid].sketch_name is None:
            _LOGGER.info('No sketch_name: node %s', nid)
            return
        if nid not in devices:
            devices[nid] = {}
        node = devices[nid]
        # Get platform specific S_TYPES, V_TYPES, class and add_devices.
        (platform_s_types,
         platform_v_types,
         platform_class,
         add_devices) = platform_type(gateway, port, devices, nid)
        for child_id, child in gateway.sensors[nid].children.items():
            if child_id not in node:
                node[child_id] = {}
            for value_type in child.values.keys():
                if (value_type not in node[child_id] and
                        child.type in platform_s_types and
                        value_type in platform_v_types):
                    name = '{} {}.{}'.format(
                        gateway.sensors[nid].sketch_name, nid, child.id)
                    node[child_id][value_type] = platform_class(
                        port, nid, child_id, name, value_type)
                    _LOGGER.info('adding new device: %s',
                                 node[child_id][value_type])
                    add_devices([node[child_id][value_type]])
                if (child.type in platform_s_types and
                        value_type in platform_v_types):
                    node[child_id][value_type].update_sensor(
                        child.values, gateway.sensors[nid].battery_level)
    return wrapper
