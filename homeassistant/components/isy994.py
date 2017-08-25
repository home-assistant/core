"""
Support the ISY-994 controllers.

For configuration details please visit the documentation for this component at
https://home-assistant.io/components/isy994/
"""
from collections import namedtuple
import logging
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.core import HomeAssistant  # noqa
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import discovery, config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, Dict  # noqa

REQUIREMENTS = ['PyISY==1.0.7']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'isy994'

CONF_HIDDEN_STRING = 'hidden_string'
CONF_SENSOR_STRING = 'sensor_string'
CONF_TLS_VER = 'tls'

DEFAULT_HIDDEN_STRING = '{HIDE ME}'
DEFAULT_SENSOR_STRING = 'sensor'

ISY = None

KEY_ACTIONS = 'actions'
KEY_FOLDER = 'folder'
KEY_MY_PROGRAMS = 'My Programs'
KEY_STATUS = 'status'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.url,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TLS_VER): vol.Coerce(float),
        vol.Optional(CONF_HIDDEN_STRING,
                     default=DEFAULT_HIDDEN_STRING): cv.string,
        vol.Optional(CONF_SENSOR_STRING,
                     default=DEFAULT_SENSOR_STRING): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

SENSOR_NODES = []
WEATHER_NODES = []
NODES = []
GROUPS = []
PROGRAMS = {}

PYISY = None

HIDDEN_STRING = DEFAULT_HIDDEN_STRING

SUPPORTED_DOMAINS = ['binary_sensor', 'cover', 'fan', 'light', 'lock',
                     'sensor', 'switch']


WeatherNode = namedtuple('WeatherNode', ('status', 'name', 'uom'))


def filter_nodes(nodes: list, units: list=None, states: list=None) -> list:
    """Filter a list of ISY nodes based on the units and states provided."""
    filtered_nodes = []
    units = units if units else []
    states = states if states else []
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


def _categorize_nodes(hidden_identifier: str, sensor_identifier: str) -> None:
    """Categorize the ISY994 nodes."""
    global SENSOR_NODES
    global NODES
    global GROUPS

    SENSOR_NODES = []
    NODES = []
    GROUPS = []

    # pylint: disable=no-member
    for (path, node) in ISY.nodes:
        hidden = hidden_identifier in path or hidden_identifier in node.name
        if hidden:
            node.name += hidden_identifier
        if sensor_identifier in path or sensor_identifier in node.name:
            SENSOR_NODES.append(node)
        elif isinstance(node, PYISY.Nodes.Node):
            NODES.append(node)
        elif isinstance(node, PYISY.Nodes.Group):
            GROUPS.append(node)


def _categorize_programs() -> None:
    """Categorize the ISY994 programs."""
    global PROGRAMS

    PROGRAMS = {}

    for component in SUPPORTED_DOMAINS:
        try:
            folder = ISY.programs[KEY_MY_PROGRAMS]['HA.' + component]
        except KeyError:
            pass
        else:
            for dtype, _, node_id in folder.children:
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


def _categorize_weather() -> None:
    """Categorize the ISY994 weather data."""
    global WEATHER_NODES

    climate_attrs = dir(ISY.climate)
    WEATHER_NODES = [WeatherNode(getattr(ISY.climate, attr), attr,
                                 getattr(ISY.climate, attr + '_units'))
                     for attr in climate_attrs
                     if attr + '_units' in climate_attrs]


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ISY 994 platform."""
    isy_config = config.get(DOMAIN)

    user = isy_config.get(CONF_USERNAME)
    password = isy_config.get(CONF_PASSWORD)
    tls_version = isy_config.get(CONF_TLS_VER)
    host = urlparse(isy_config.get(CONF_HOST))
    port = host.port
    addr = host.geturl()
    hidden_identifier = isy_config.get(
        CONF_HIDDEN_STRING, DEFAULT_HIDDEN_STRING)
    sensor_identifier = isy_config.get(
        CONF_SENSOR_STRING, DEFAULT_SENSOR_STRING)

    global HIDDEN_STRING
    HIDDEN_STRING = hidden_identifier

    if host.scheme == 'http':
        addr = addr.replace('http://', '')
        https = False
    elif host.scheme == 'https':
        addr = addr.replace('https://', '')
        https = True
    else:
        _LOGGER.error("isy994 host value in configuration is invalid")
        return False

    addr = addr.replace(':{}'.format(port), '')

    import PyISY

    global PYISY
    PYISY = PyISY

    # Connect to ISY controller.
    global ISY
    ISY = PyISY.ISY(addr, port, username=user, password=password,
                    use_https=https, tls_ver=tls_version, log=_LOGGER)
    if not ISY.connected:
        return False

    _categorize_nodes(hidden_identifier, sensor_identifier)

    _categorize_programs()

    if ISY.configuration.get('Weather Information'):
        _categorize_weather()

    # Listen for HA stop to disconnect.
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop)

    # Load platforms for the devices in the ISY controller that we support.
    for component in SUPPORTED_DOMAINS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    ISY.auto_update = True
    return True


# pylint: disable=unused-argument
def stop(event: object) -> None:
    """Stop ISY auto updates."""
    ISY.auto_update = False


class ISYDevice(Entity):
    """Representation of an ISY994 device."""

    _attrs = {}
    _domain = None  # type: str
    _name = None  # type: str

    def __init__(self, node) -> None:
        """Initialize the insteon device."""
        self._node = node

        self._change_handler = self._node.status.subscribe(
            'changed', self.on_update)

    # pylint: disable=unused-argument
    def on_update(self, event: object) -> None:
        """Handle the update event from the ISY994 Node."""
        self.schedule_update_ha_state()

    @property
    def domain(self) -> str:
        """Get the domain of the device."""
        return self._domain

    @property
    def unique_id(self) -> str:
        """Get the unique identifier of the device."""
        # pylint: disable=protected-access
        return self._node._id

    @property
    def raw_name(self) -> str:
        """Get the raw name of the device."""
        return str(self._name) \
            if self._name is not None else str(self._node.name)

    @property
    def name(self) -> str:
        """Get the name of the device."""
        return self.raw_name.replace(HIDDEN_STRING, '').strip() \
            .replace('_', ' ')

    @property
    def should_poll(self) -> bool:
        """No polling required since we're using the subscription."""
        return False

    @property
    def value(self) -> object:
        """Get the current value of the device."""
        # pylint: disable=protected-access
        return self._node.status._val

    @property
    def device_state_attributes(self) -> Dict:
        """Get the state attributes for the device."""
        attr = {}
        if hasattr(self._node, 'aux_properties'):
            for name, val in self._node.aux_properties.items():
                attr[name] = '{} {}'.format(val.get('value'), val.get('uom'))
        return attr

    @property
    def hidden(self) -> bool:
        """Get whether the device should be hidden from the UI."""
        return HIDDEN_STRING in self.raw_name

    @property
    def unit_of_measurement(self) -> str:
        """Get the device unit of measure."""
        return None

    def _attr_filter(self, attr: str) -> str:
        """Filter the attribute."""
        # pylint: disable=no-self-use
        return attr

    def update(self) -> None:
        """Perform an update for the device."""
        pass
