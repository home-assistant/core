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

try:
    import mysensors.mysensors as mysensors
except ImportError:
    mysensors = None

from homeassistant.helpers import validate_config
import homeassistant.bootstrap as bootstrap

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_PLATFORM_DISCOVERED, ATTR_SERVICE, ATTR_DISCOVERED,
    TEMP_CELCIUS,)

CONF_GATEWAYS = 'gateways'
CONF_PORT = 'port'
CONF_DEBUG = 'debug'
CONF_PERSISTENCE = 'persistence'
CONF_PERSISTENCE_FILE = 'persistence_file'
CONF_VERSION = 'version'
DEFAULT_VERSION = '1.4'

DOMAIN = 'mysensors'
DEPENDENCIES = []
REQUIREMENTS = [
    'https://github.com/theolind/pymysensors/archive/'
    '2aa8f32908e8c5bb3e5c77c5851db778f8635792.zip#pymysensors==0.3']
_LOGGER = logging.getLogger(__name__)
ATTR_NODE_ID = 'node_id'
ATTR_CHILD_ID = 'child_id'

GATEWAYS = None
SCAN_INTERVAL = 30

DISCOVER_SENSORS = "mysensors.sensors"
DISCOVER_SWITCHES = "mysensors.switches"

# Maps discovered services to their platforms
DISCOVERY_COMPONENTS = [
    ('sensor', DISCOVER_SENSORS),
    ('switch', DISCOVER_SWITCHES),
]


def setup(hass, config):
    """Setup the MySensors component."""
    # pylint: disable=too-many-locals

    if not validate_config(config,
                           {DOMAIN: [CONF_GATEWAYS]},
                           _LOGGER):
        return False

    global mysensors  # pylint: disable=invalid-name
    if mysensors is None:
        import mysensors.mysensors as _mysensors
        mysensors = _mysensors

    version = str(config[DOMAIN].get(CONF_VERSION, DEFAULT_VERSION))
    is_metric = (hass.config.temperature_unit == TEMP_CELCIUS)

    def setup_gateway(port, persistence, persistence_file, version):
        """Return gateway after setup of the gateway."""
        gateway = GatewayWrapper(
            port, persistence, persistence_file, version)
        # pylint: disable=attribute-defined-outside-init
        gateway.metric = is_metric
        gateway.debug = config[DOMAIN].get(CONF_DEBUG, False)

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
        GATEWAYS[port] = setup_gateway(
            port, persistence, persistence_file, version)

    for (component, discovery_service) in DISCOVERY_COMPONENTS:
        # Ensure component is loaded
        if not bootstrap.setup_component(hass, component, config):
            return False
        # Fire discovery event
        hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
            ATTR_SERVICE: discovery_service,
            ATTR_DISCOVERED: {}})

    return True


def pf_callback_factory(
        s_types, v_types, devices, add_devices, entity_class):
    """Return a new callback for the platform."""
    def mysensors_callback(gateway, node_id):
        """Callback for mysensors platform."""
        if gateway.sensors[node_id].sketch_name is None:
            _LOGGER.info('No sketch_name: node %s', node_id)
            return
        # previously discovered, just update state with latest info
        if node_id in devices:
            for entity in devices[node_id]:
                entity.update_ha_state(True)
            return

        # First time we see this node, detect sensors
        for child in gateway.sensors[node_id].children.values():
            name = '{} {}.{}'.format(
                gateway.sensors[node_id].sketch_name, node_id, child.id)

            for value_type in child.values.keys():
                if child.type not in s_types or value_type not in v_types:
                    continue

                devices[node_id].append(
                    entity_class(gateway, node_id, child.id, name, value_type))
        if devices[node_id]:
            _LOGGER.info('adding new devices: %s', devices[node_id])
            add_devices(devices[node_id])
        for entity in devices[node_id]:
            entity.update_ha_state(True)
    return mysensors_callback


class GatewayWrapper(mysensors.SerialGateway):
    """Gateway wrapper class, by subclassing serial gateway."""

    def __init__(self, port, persistence, persistence_file, version):
        """Setup class attributes on instantiation.

        Args:
        port: Port of gateway to wrap.
        persistence: Persistence, true or false.
        persistence_file: File to store persistence info.
        version: Version of mysensors API.

        Attributes:
        version (str): Version of mysensors API.
        platform_callbacks (list): Callback functions, one per platform.
        const (module): Mysensors API constants.
        """
        super().__init__(port, event_callback=self.callback_factory(),
                         persistence=persistence,
                         persistence_file=persistence_file,
                         protocol_version=version)
        self.version = version
        self.platform_callbacks = []
        self.const = self.get_const()

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
            _LOGGER.info('update %s: node %s', update_type, node_id)
            for callback in self.platform_callbacks:
                callback(self, node_id)

        return node_update
