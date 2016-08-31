"""
Support the ISY-994 controllers.

For configuration details please visit the documentation for this component at
https://home-assistant.io/components/isy994/
"""
import logging
from urllib.parse import urlparse
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import discovery, config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, Dict  # noqa

DOMAIN = "isy994"
REQUIREMENTS = ['PyISY==1.0.7']

ISY = None
DEFAULT_SENSOR_STRING = 'sensor'
DEFAULT_HIDDEN_STRING = '{HIDE ME}'
CONF_TLS_VER = 'tls'
CONF_HIDDEN_STRING = 'hidden_string'
CONF_SENSOR_STRING = 'sensor_string'
KEY_MY_PROGRAMS = 'My Programs'
KEY_FOLDER = 'folder'
KEY_ACTIONS = 'actions'
KEY_STATUS = 'status'

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.url,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TLS_VER, None): vol.Coerce(float),
        vol.Optional(CONF_HIDDEN_STRING, DEFAULT_HIDDEN_STRING): cv.string,
        vol.Optional(CONF_SENSOR_STRING, DEFAULT_SENSOR_STRING): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

SENSOR_NODES = []
NODES = []
GROUPS = []
PROGRAMS = {}

HIDDEN_STRING = DEFAULT_HIDDEN_STRING

COMPONENTS = ['lock', 'binary_sensor', 'cover', 'fan', 'sensor', 'light', 'switch']
# '('binary_sensor', 'climate', 'cover', 'fan', 'light',
#                       'lock', 'sensor')


def filter_nodes(nodes: list, units: list=[], states: list=[]) -> list:
    """Filter nodes for the specified units or states."""
    filtered_nodes = []
    for node in nodes:
        match_unit = False
        match_state = True
        for uom in node.uom:
            if uom in units:
                match_unit = True
                continue
            elif uom not in states:
                match_state = False

            if match_unit:
                continue

        if match_unit or match_state:
            filtered_nodes.append(node)

    return filtered_nodes


def setup(hass, config: ConfigType) -> bool:
    """Setup ISY994 component.

    This will automatically import associated lights, switches, and sensors.
    """
    isy_config = config.get(DOMAIN)

    user = isy_config.get(CONF_USERNAME)
    password = isy_config.get(CONF_PASSWORD)
    tls_version = isy_config.get(CONF_TLS_VER)
    host = urlparse(isy_config.get(CONF_HOST))
    port = host.port
    addr = host.geturl()
    hidden_identifier = isy_config.get(CONF_HIDDEN_STRING,
                                       DEFAULT_HIDDEN_STRING)
    sensor_identifier = isy_config.get(CONF_SENSOR_STRING,
                                       DEFAULT_SENSOR_STRING)

    global HIDDEN_STRING
    HIDDEN_STRING = hidden_identifier

    if host.scheme == 'http':
        addr = addr.replace('http://', '')
        https = False
    elif host.scheme == 'https':
        addr = addr.replace('https://', '')
        https = True
    else:
        _LOGGER.error('isy994 host value in configuration is invalid.')
        return False

    addr = addr.replace(':{}'.format(port), '')

    import PyISY

    # Connect to ISY controller.
    global ISY
    ISY = PyISY.ISY(addr, port, user, password, use_https=https,
                    tls_ver=tls_version, log=_LOGGER)
    if not ISY.connected:
        return False

    global SENSOR_NODES
    global NODES
    global GROUPS
    global PROGRAMS

    SENSOR_NODES = []
    NODES = []
    GROUPS = []
    PROGRAMS = {}

    for (path, node) in ISY.nodes:
        hidden = hidden_identifier in path or hidden_identifier in node.name
        if hidden:
            node.name += hidden_identifier
        if sensor_identifier in path or sensor_identifier in node.name:
            SENSOR_NODES.append(node)
        elif isinstance(node, PyISY.Nodes.Node):
            NODES.append(node)
        elif isinstance(node, PyISY.Nodes.Group):
            GROUPS.append(node)

    for component in COMPONENTS:
        try:
            folder = ISY.programs[KEY_MY_PROGRAMS][component]
        except KeyError:
            pass
        else:
            for dtype, name, node_id in folder.children:
                if dtype is KEY_FOLDER:
                    program = folder[node_id]
                    try:
                        node = program[KEY_STATUS].leaf
                        assert node.dtype == 'program', 'Not a program'
                    except (KeyError, AssertionError):
                        pass
                    else:
                        if component not in PROGRAMS:
                            PROGRAMS[component] = []
                        PROGRAMS[component].append(program)

    # Listen for HA stop to disconnect.
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop)

    # Load platforms for the devices in the ISY controller that we support.
    for component in COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    ISY.auto_update = True
    return True


# pylint: disable=unused-argument
def stop(event: object) -> None:
    """Cleanup the ISY subscription."""
    ISY.auto_update = False


class ISYDevice(Entity):
    """Base class for all isy994 devices."""

    import PyISY.Nodes.node  # noqa

    _attrs = {}
    _domain = None
    _name = None

    def __init__(self, node: PyISY.Nodes.node) -> None:
        """Initialize the isy device."""
        self._node = node

        self._change_handler = self._node.status.subscribe('changed',
                                                           self.on_update)

    def __del__(self) -> None:
        """Cleanup subscriptions."""
        self._change_handler.unsubscribe()

    # pylint: disable=unused-argument
    def on_update(self, event: object) -> None:
        """Handle the update received event."""
        self.update_ha_state()

    @property
    def domain(self) -> str:
        """Return the domain of the device."""
        return self._domain

    @property
    def unique_id(self):
        """Return the node id."""
        # pylint: disable=protected-access
        return self._node._id

    @property
    def raw_name(self):
        """Return the raw node name."""
        return str(self._name) \
            if self._name is not None else str(self._node.name)

    @property
    def name(self):
        """Return the cleaned name of the node."""
        return self.raw_name.replace(HIDDEN_STRING, '').strip() \
            .replace('_', ' ')

    @property
    def should_poll(self) -> bool:
        """No polling required."""
        return False

    @property
    def value(self) -> object:
        """Return the raw value from the controller"""
        # pylint: disable=protected-access
        return self._node.status._val

    @property
    def state_attributes(self) -> Dict:
        """Return the state attributes for the node."""
        attr = {}
        if hasattr(self._node, 'aux_properties'):
            for name, val in self._node.aux_properties.items():
                attr[name] = '{} {}'.format(val.get('value'), val.get('uom'))
        return attr

    @property
    def hidden(self):
        """Flag to hide entity from UI."""
        return HIDDEN_STRING in self.raw_name

    @property
    def unit_of_measurement(self):
        """Default to no unit of measure."""
        return None

    def _attr_filter(self, attr):
        """A Placeholder for attribute filters."""
        # pylint: disable=no-self-use
        return attr

    def update(self):
        """Update the state of the device."""
        pass
