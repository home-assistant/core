"""
Connect to a MySensors gateway via pymysensors API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mysensors/
"""
import logging

import homeassistant.bootstrap as bootstrap
from homeassistant.const import (
    ATTR_DISCOVERED, ATTR_SERVICE, EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP, EVENT_PLATFORM_DISCOVERED, TEMP_CELCIUS)
from homeassistant.helpers import validate_config

CONF_GATEWAYS = 'gateways'
CONF_PORT = 'port'
CONF_DEBUG = 'debug'
CONF_PERSISTENCE = 'persistence'
CONF_PERSISTENCE_FILE = 'persistence_file'
CONF_VERSION = 'version'
CONF_BAUD_RATE = 'baud_rate'
CONF_OPTIMISTIC = 'optimistic'
DEFAULT_VERSION = '1.4'
DEFAULT_BAUD_RATE = 115200

DOMAIN = 'mysensors'
DEPENDENCIES = []
REQUIREMENTS = [
    'https://github.com/theolind/pymysensors/archive/'
    'f0c928532167fb24823efa793ec21ca646fd37a6.zip#pymysensors==0.5']
_LOGGER = logging.getLogger(__name__)
ATTR_NODE_ID = 'node_id'
ATTR_CHILD_ID = 'child_id'
ATTR_PORT = 'port'

GATEWAYS = None

DISCOVER_SENSORS = 'mysensors.sensors'
DISCOVER_SWITCHES = 'mysensors.switches'
DISCOVER_LIGHTS = 'mysensors.lights'
DISCOVER_BINARY_SENSORS = 'mysensors.binary_sensor'

# Maps discovered services to their platforms
DISCOVERY_COMPONENTS = [
    ('sensor', DISCOVER_SENSORS),
    ('switch', DISCOVER_SWITCHES),
    ('light', DISCOVER_LIGHTS),
    ('binary_sensor', DISCOVER_BINARY_SENSORS),
]


def setup(hass, config):
    """Setup the MySensors component."""
    if not validate_config(config,
                           {DOMAIN: [CONF_GATEWAYS]},
                           _LOGGER):
        return False
    if not all(CONF_PORT in gateway
               for gateway in config[DOMAIN][CONF_GATEWAYS]):
        _LOGGER.error('Missing required configuration items '
                      'in %s: %s', DOMAIN, CONF_PORT)
        return False

    import mysensors.mysensors as mysensors

    version = str(config[DOMAIN].get(CONF_VERSION, DEFAULT_VERSION))
    is_metric = (hass.config.temperature_unit == TEMP_CELCIUS)

    def setup_gateway(port, persistence, persistence_file, version, baud_rate):
        """Return gateway after setup of the gateway."""
        gateway = mysensors.SerialGateway(port, event_callback=None,
                                          persistence=persistence,
                                          persistence_file=persistence_file,
                                          protocol_version=version,
                                          baud=baud_rate)
        gateway.metric = is_metric
        gateway.debug = config[DOMAIN].get(CONF_DEBUG, False)
        optimistic = config[DOMAIN].get(CONF_OPTIMISTIC, False)
        gateway = GatewayWrapper(gateway, version, optimistic)
        # pylint: disable=attribute-defined-outside-init
        gateway.event_callback = gateway.callback_factory()

        def gw_start(event):
            """Callback to trigger start of gateway and any persistence."""
            gateway.start()
            hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                                 lambda event: gateway.stop())
            if persistence:
                for node_id in gateway.sensors:
                    gateway.event_callback('persistence', node_id)

        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, gw_start)

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
        baud_rate = gway.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE)
        GATEWAYS[port] = setup_gateway(
            port, persistence, persistence_file, version, baud_rate)

    for (component, discovery_service) in DISCOVERY_COMPONENTS:
        # Ensure component is loaded
        if not bootstrap.setup_component(hass, component, config):
            return False
        # Fire discovery event
        hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
            ATTR_SERVICE: discovery_service,
            ATTR_DISCOVERED: {}})

    return True


def pf_callback_factory(map_sv_types, devices, add_devices, entity_class):
    """Return a new callback for the platform."""
    def mysensors_callback(gateway, node_id):
        """Callback for mysensors platform."""
        if gateway.sensors[node_id].sketch_name is None:
            _LOGGER.info('No sketch_name: node %s', node_id)
            return

        for child in gateway.sensors[node_id].children.values():
            for value_type in child.values.keys():
                key = node_id, child.id, value_type
                if child.type not in map_sv_types or \
                        value_type not in map_sv_types[child.type]:
                    continue
                if key in devices:
                    devices[key].update_ha_state(True)
                    continue
                name = '{} {}.{}'.format(
                    gateway.sensors[node_id].sketch_name, node_id, child.id)
                if isinstance(entity_class, dict):
                    device_class = entity_class[child.type]
                else:
                    device_class = entity_class
                devices[key] = device_class(
                    gateway, node_id, child.id, name, value_type, child.type)

                _LOGGER.info('Adding new devices: %s', devices[key])
                add_devices([devices[key]])
                if key in devices:
                    devices[key].update_ha_state(True)
    return mysensors_callback


class GatewayWrapper(object):
    """Gateway wrapper class."""

    def __init__(self, gateway, version, optimistic):
        """Setup class attributes on instantiation.

        Args:
        gateway (mysensors.SerialGateway): Gateway to wrap.
        version (str): Version of mysensors API.
        optimistic (bool): Send values to actuators without feedback state.

        Attributes:
        _wrapped_gateway (mysensors.SerialGateway): Wrapped gateway.
        version (str): Version of mysensors API.
        platform_callbacks (list): Callback functions, one per platform.
        const (module): Mysensors API constants.
        optimistic (bool): Send values to actuators without feedback state.
        __initialised (bool): True if GatewayWrapper is initialised.
        """
        self._wrapped_gateway = gateway
        self.version = version
        self.platform_callbacks = []
        self.const = self.get_const()
        self.optimistic = optimistic
        self.__initialised = True

    def __getattr__(self, name):
        """See if this object has attribute name."""
        # Do not use hasattr, it goes into infinite recurrsion
        if name in self.__dict__:
            # this object has it
            return getattr(self, name)
        # proxy to the wrapped object
        return getattr(self._wrapped_gateway, name)

    def __setattr__(self, name, value):
        """See if this object has attribute name then set to value."""
        if '_GatewayWrapper__initialised' not in self.__dict__:
            return object.__setattr__(self, name, value)
        elif name in self.__dict__:
            object.__setattr__(self, name, value)
        else:
            object.__setattr__(self._wrapped_gateway, name, value)

    def get_const(self):
        """Get mysensors API constants."""
        if self.version == '1.5':
            import mysensors.const_15 as const
        else:
            import mysensors.const_14 as const
        return const

    def callback_factory(self):
        """Return a new callback function."""
        def node_update(update_type, node_id):
            """Callback for node updates from the MySensors gateway."""
            _LOGGER.debug('update %s: node %s', update_type, node_id)
            for callback in self.platform_callbacks:
                callback(self, node_id)

        return node_update
