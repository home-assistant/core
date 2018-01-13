"""
Support the ISY-994 controllers.

For configuration details please visit the documentation for this component at
https://home-assistant.io/components/isy994/
"""
import asyncio
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

REQUIREMENTS = ['PyISY==1.1.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'isy994'

CONF_IGNORE_STRING = 'ignore_string'
CONF_SENSOR_STRING = 'sensor_string'
CONF_ENABLE_CLIMATE = 'enable_climate'
CONF_TLS_VER = 'tls'

DEFAULT_IGNORE_STRING = '{IGNORE ME}'
DEFAULT_SENSOR_STRING = 'sensor'

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
        vol.Optional(CONF_IGNORE_STRING,
                     default=DEFAULT_IGNORE_STRING): cv.string,
        vol.Optional(CONF_SENSOR_STRING,
                     default=DEFAULT_SENSOR_STRING): cv.string,
        vol.Optional(CONF_ENABLE_CLIMATE,
                     default=True): cv.boolean
    })
}, extra=vol.ALLOW_EXTRA)

# Do not use the Hass consts for the states here - we're matching exact API
# responses, not using them for Hass states
NODE_FILTERS = {
    'binary_sensor': {
        'uom': [],
        'states': [],
        'node_def_id': ['BinaryAlarm'],
        'insteon_type': ['16.']  # Does a startswith() match; include the dot
    },
    'sensor': {
        # This is just a more-readable way of including MOST uoms between 1-100
        # (Remember that range() is non-inclusive of the stop value)
        'uom': (['1'] +
                list(map(str, range(3, 11))) +
                list(map(str, range(12, 51))) +
                list(map(str, range(52, 66))) +
                list(map(str, range(69, 78))) +
                ['79'] +
                list(map(str, range(82, 97)))),
        'states': [],
        'node_def_id': ['IMETER_SOLO'],
        'insteon_type': ['9.0.', '9.7.']
    },
    'lock': {
        'uom': ['11'],
        'states': ['locked', 'unlocked'],
        'node_def_id': ['DoorLock'],
        'insteon_type': ['15.']
    },
    'fan': {
        'uom': [],
        'states': ['on', 'off', 'low', 'medium', 'high'],
        'node_def_id': ['FanLincMotor'],
        'insteon_type': ['1.46.']
    },
    'cover': {
        'uom': ['97'],
        'states': ['open', 'closed', 'closing', 'opening', 'stopped'],
        'node_def_id': [],
        'insteon_type': []
    },
    'light': {
        'uom': ['51'],
        'states': ['on', 'off', '%'],
        'node_def_id': ['DimmerLampSwitch', 'DimmerLampSwitch_ADV',
                        'DimmerSwitchOnly', 'DimmerSwitchOnly_ADV',
                        'DimmerLampOnly', 'BallastRelayLampSwitch',
                        'BallastRelayLampSwitch_ADV', 'RelayLampSwitch',
                        'RemoteLinc2', 'RemoteLinc2_ADV'],
        'insteon_type': ['1.']
    },
    'switch': {
        'uom': ['2', '78'],
        'states': ['on', 'off'],
        'node_def_id': ['OnOffControl', 'RelayLampSwitch',
                        'RelayLampSwitch_ADV', 'RelaySwitchOnlyPlusQuery',
                        'RelaySwitchOnlyPlusQuery_ADV', 'RelayLampOnly',
                        'RelayLampOnly_ADV', 'KeypadButton',
                        'KeypadButton_ADV', 'EZRAIN_Input', 'EZRAIN_Output',
                        'EZIO2x4_Input', 'EZIO2x4_Input_ADV', 'BinaryControl',
                        'BinaryControl_ADV', 'AlertModuleSiren',
                        'AlertModuleSiren_ADV', 'AlertModuleArmed', 'Siren',
                        'Siren_ADV'],
        'insteon_type': ['2.', '9.10.', '9.11.']
    }
}

SUPPORTED_DOMAINS = ['binary_sensor', 'sensor', 'lock', 'fan', 'cover',
                     'light', 'switch']
SUPPORTED_PROGRAM_DOMAINS = ['binary_sensor', 'lock', 'fan', 'cover', 'switch']

# ISY Scenes are more like Swithes than Hass Scenes
# (they can turn off, and report their state)
SCENE_DOMAIN = 'switch'

ISY994_NODES = "isy994_nodes"
ISY994_WEATHER = "isy994_weather"
ISY994_PROGRAMS = "isy994_programs"

WeatherNode = namedtuple('WeatherNode', ('status', 'name', 'uom'))


def _check_for_node_def(hass: HomeAssistant, node,
                        single_domain: str=None) -> bool:
    """Check if the node matches the node_def_id for any domains.

    This is only present on the 5.0 ISY firmware, and is the most reliable
    way to determine a device's type.
    """
    if not hasattr(node, 'node_def_id') or node.node_def_id is None:
        # Node doesn't have a node_def (pre 5.0 firmware most likely)
        return False

    node_def_id = node.node_def_id

    domains = SUPPORTED_DOMAINS if not single_domain else [single_domain]
    for domain in domains:
        if node_def_id in NODE_FILTERS[domain]['node_def_id']:
            hass.data[ISY994_NODES][domain].append(node)
            return True

    return False


def _check_for_insteon_type(hass: HomeAssistant, node,
                            single_domain: str=None) -> bool:
    """Check if the node matches the Insteon type for any domains.

    This is for (presumably) every version of the ISY firmware, but only
    works for Insteon device. "Node Server" (v5+) and Z-Wave and others will
    not have a type.
    """
    if not hasattr(node, 'type') or node.type is None:
        # Node doesn't have a type (non-Insteon device most likely)
        return False

    device_type = node.type
    domains = SUPPORTED_DOMAINS if not single_domain else [single_domain]
    for domain in domains:
        if any([device_type.startswith(t) for t in
                set(NODE_FILTERS[domain]['insteon_type'])]):
            hass.data[ISY994_NODES][domain].append(node)
            return True

    return False


def _check_for_uom_id(hass: HomeAssistant, node,
                      single_domain: str=None, uom_list: list=None) -> bool:
    """Check if a node's uom matches any of the domains uom filter.

    This is used for versions of the ISY firmware that report uoms as a single
    ID. We can often infer what type of device it is by that ID.
    """
    if not hasattr(node, 'uom') or node.uom is None:
        # Node doesn't have a uom (Scenes for example)
        return False

    node_uom = set(map(str.lower, node.uom))

    if uom_list:
        if node_uom.intersection(NODE_FILTERS[single_domain]['uom']):
            hass.data[ISY994_NODES][single_domain].append(node)
            return True
    else:
        domains = SUPPORTED_DOMAINS if not single_domain else [single_domain]
        for domain in domains:
            if node_uom.intersection(NODE_FILTERS[domain]['uom']):
                hass.data[ISY994_NODES][domain].append(node)
                return True

    return False


def _check_for_states_in_uom(hass: HomeAssistant, node,
                             single_domain: str=None,
                             states_list: list=None) -> bool:
    """Check if a list of uoms matches two possible filters.

    This is for versions of the ISY firmware that report uoms as a list of all
    possible "human readable" states. This filter passes if all of the possible
    states fit inside the given filter.
    """
    if not hasattr(node, 'uom') or node.uom is None:
        # Node doesn't have a uom (Scenes for example)
        return False

    node_uom = set(map(str.lower, node.uom))

    if states_list:
        if node_uom == set(states_list):
            hass.data[ISY994_NODES][single_domain].append(node)
            return True
    else:
        domains = SUPPORTED_DOMAINS if not single_domain else [single_domain]
        for domain in domains:
            if node_uom == set(NODE_FILTERS[domain]['states']):
                hass.data[ISY994_NODES][domain].append(node)
                return True

    return False


def _is_sensor_a_binary_sensor(hass: HomeAssistant, node) -> bool:
    """Determine if the given sensor node should be a binary_sensor."""
    if _check_for_node_def(hass, node, single_domain='binary_sensor'):
        return True
    if _check_for_insteon_type(hass, node, single_domain='binary_sensor'):
        return True

    # For the next two checks, we're providing our own set of uoms that
    # represent on/off devices. This is because we can only depend on these
    # checks in the context of already knowing that this is definitely a
    # sensor device.
    if _check_for_uom_id(hass, node, single_domain='binary_sensor',
                         uom_list=['2', '78']):
        return True
    if _check_for_states_in_uom(hass, node, single_domain='binary_sensor',
                                states_list=['on', 'off']):
        return True

    return False


def _categorize_nodes(hass: HomeAssistant, nodes, ignore_identifier: str,
                      sensor_identifier: str)-> None:
    """Sort the nodes to their proper domains."""
    # pylint: disable=no-member
    for (path, node) in nodes:
        ignored = ignore_identifier in path or ignore_identifier in node.name
        if ignored:
            # Don't import this node as a device at all
            continue

        from PyISY.Nodes import Group
        if isinstance(node, Group):
            hass.data[ISY994_NODES][SCENE_DOMAIN].append(node)
            continue

        if sensor_identifier in path or sensor_identifier in node.name:
            # User has specified to treat this as a sensor. First we need to
            # determine if it should be a binary_sensor.
            if _is_sensor_a_binary_sensor(hass, node):
                continue
            else:
                hass.data[ISY994_NODES]['sensor'].append(node)
                continue

        # We have a bunch of different methods for determining the device type,
        # each of which works with different ISY firmware versions or device
        # family. The order here is important, from most reliable to least.
        if _check_for_node_def(hass, node):
            continue
        if _check_for_insteon_type(hass, node):
            continue
        if _check_for_uom_id(hass, node):
            continue
        if _check_for_states_in_uom(hass, node):
            continue


def _categorize_programs(hass: HomeAssistant, programs: dict) -> None:
    """Categorize the ISY994 programs."""
    for domain in SUPPORTED_PROGRAM_DOMAINS:
        try:
            folder = programs[KEY_MY_PROGRAMS]['HA.{}'.format(domain)]
        except KeyError:
            pass
        else:
            for dtype, _, node_id in folder.children:
                if dtype == KEY_FOLDER:
                    entity_folder = folder[node_id]
                    try:
                        status = entity_folder[KEY_STATUS]
                        assert status.dtype == 'program', 'Not a program'
                        if domain != 'binary_sensor':
                            actions = entity_folder[KEY_ACTIONS]
                            assert actions.dtype == 'program', 'Not a program'
                        else:
                            actions = None
                    except (AttributeError, KeyError, AssertionError):
                        _LOGGER.warning("Program entity '%s' not loaded due "
                                        "to invalid folder structure.",
                                        entity_folder.name)
                        continue

                    entity = (entity_folder.name, status, actions)
                    hass.data[ISY994_PROGRAMS][domain].append(entity)


def _categorize_weather(hass: HomeAssistant, climate) -> None:
    """Categorize the ISY994 weather data."""
    climate_attrs = dir(climate)
    weather_nodes = [WeatherNode(getattr(climate, attr),
                                 attr.replace('_', ' '),
                                 getattr(climate, '{}_units'.format(attr)))
                     for attr in climate_attrs
                     if '{}_units'.format(attr) in climate_attrs]
    hass.data[ISY994_WEATHER].extend(weather_nodes)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ISY 994 platform."""
    hass.data[ISY994_NODES] = {}
    for domain in SUPPORTED_DOMAINS:
        hass.data[ISY994_NODES][domain] = []

    hass.data[ISY994_WEATHER] = []

    hass.data[ISY994_PROGRAMS] = {}
    for domain in SUPPORTED_DOMAINS:
        hass.data[ISY994_PROGRAMS][domain] = []

    isy_config = config.get(DOMAIN)

    user = isy_config.get(CONF_USERNAME)
    password = isy_config.get(CONF_PASSWORD)
    tls_version = isy_config.get(CONF_TLS_VER)
    host = urlparse(isy_config.get(CONF_HOST))
    ignore_identifier = isy_config.get(CONF_IGNORE_STRING)
    sensor_identifier = isy_config.get(CONF_SENSOR_STRING)
    enable_climate = isy_config.get(CONF_ENABLE_CLIMATE)

    if host.scheme == 'http':
        https = False
        port = host.port or 80
    elif host.scheme == 'https':
        https = True
        port = host.port or 443
    else:
        _LOGGER.error("isy994 host value in configuration is invalid")
        return False

    import PyISY
    # Connect to ISY controller.
    isy = PyISY.ISY(host.hostname, port, username=user, password=password,
                    use_https=https, tls_ver=tls_version, log=_LOGGER)
    if not isy.connected:
        return False

    _categorize_nodes(hass, isy.nodes, ignore_identifier, sensor_identifier)
    _categorize_programs(hass, isy.programs)

    if enable_climate and isy.configuration.get('Weather Information'):
        _categorize_weather(hass, isy.climate)

    def stop(event: object) -> None:
        """Stop ISY auto updates."""
        isy.auto_update = False

    # Listen for HA stop to disconnect.
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop)

    # Load platforms for the devices in the ISY controller that we support.
    for component in SUPPORTED_DOMAINS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    isy.auto_update = True
    return True


class ISYDevice(Entity):
    """Representation of an ISY994 device."""

    _attrs = {}
    _name = None  # type: str

    def __init__(self, node) -> None:
        """Initialize the insteon device."""
        self._node = node
        self._change_handler = None
        self._control_handler = None

    @asyncio.coroutine
    def async_added_to_hass(self) -> None:
        """Subscribe to the node change events."""
        self._change_handler = self._node.status.subscribe(
            'changed', self.on_update)

        if hasattr(self._node, 'controlEvents'):
            self._control_handler = self._node.controlEvents.subscribe(
                self.on_control)

    # pylint: disable=unused-argument
    def on_update(self, event: object) -> None:
        """Handle the update event from the ISY994 Node."""
        self.schedule_update_ha_state()

    def on_control(self, event: object) -> None:
        """Handle a control event from the ISY994 Node."""
        self.hass.bus.fire('isy994_control', {
            'entity_id': self.entity_id,
            'control': event
        })

    @property
    def unique_id(self) -> str:
        """Get the unique identifier of the device."""
        # pylint: disable=protected-access
        return self._node._id

    @property
    def name(self) -> str:
        """Get the name of the device."""
        return self._name or str(self._node.name)

    @property
    def should_poll(self) -> bool:
        """No polling required since we're using the subscription."""
        return False

    @property
    def value(self) -> int:
        """Get the current value of the device."""
        # pylint: disable=protected-access
        return self._node.status._val

    def is_unknown(self) -> bool:
        """Get whether or not the value of this Entity's node is unknown.

        PyISY reports unknown values as -inf
        """
        return self.value == -1 * float('inf')

    @property
    def state(self):
        """Return the state of the ISY device."""
        if self.is_unknown():
            return None
        else:
            return super().state

    @property
    def device_state_attributes(self) -> Dict:
        """Get the state attributes for the device."""
        attr = {}
        if hasattr(self._node, 'aux_properties'):
            for name, val in self._node.aux_properties.items():
                attr[name] = '{} {}'.format(val.get('value'), val.get('uom'))
        return attr
