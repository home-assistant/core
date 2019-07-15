"""Support the ISY-994 controllers."""
from collections import namedtuple
import logging
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DCS)
from homeassistant.components.sensor import DEVICE_CLASSES_SCHEMA as SENSOR_DCS
from homeassistant.const import (
    CONF_BINARY_SENSORS, CONF_DEVICE_CLASS, CONF_HOST, CONF_ICON, CONF_ID,
    CONF_NAME, CONF_PASSWORD, CONF_PAYLOAD_OFF, CONF_PAYLOAD_ON, CONF_SENSORS,
    CONF_SWITCHES, CONF_TYPE, CONF_UNIT_OF_MEASUREMENT, CONF_USERNAME,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP, STATE_UNKNOWN)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, Dict

from .const import (
    CONF_ENABLE_CLIMATE, CONF_IGNORE_STRING, CONF_ISY_VARIABLES,
    CONF_SENSOR_STRING, CONF_TLS_VER, DEFAULT_IGNORE_STRING, DEFAULT_OFF_VALUE,
    DEFAULT_ON_VALUE, DEFAULT_SENSOR_STRING, DOMAIN, INSTEON_RAMP_RATES,
    ISY994_EVENT_FRIENDLY_NAME, ISY994_EVENT_IGNORE, ISY994_NODES,
    ISY994_PROGRAMS, ISY994_VARIABLES, ISY994_WEATHER, KEY_ACTIONS, KEY_FOLDER,
    KEY_MY_PROGRAMS, KEY_STATUS, NODE_FILTERS, SCENE_DOMAIN, SUPPORTED_DOMAINS,
    SUPPORTED_PROGRAM_DOMAINS, SUPPORTED_VARIABLE_DOMAINS, UOM_FRIENDLY_NAME,
    UOM_TO_STATES)

_LOGGER = logging.getLogger(__name__)

VAR_BASE_SCHEMA = vol.Schema({
    vol.Required(CONF_ID): cv.positive_int,
    vol.Required(CONF_TYPE): vol.All(cv.positive_int,
                                     vol.In([1, 2])),
    vol.Optional(CONF_ICON): cv.icon,
    vol.Optional(CONF_NAME): cv.string,
    })

SENSOR_VAR_SCHEMA = VAR_BASE_SCHEMA.extend({
    vol.Optional(CONF_DEVICE_CLASS): SENSOR_DCS,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    })

BINARY_SENSOR_VAR_SCHEMA = VAR_BASE_SCHEMA.extend({
    vol.Optional(CONF_DEVICE_CLASS): BINARY_SENSOR_DCS,
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_ON_VALUE): vol.Coerce(int),
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_OFF_VALUE): vol.Coerce(int),
    })

SWITCH_VAR_SCHEMA = VAR_BASE_SCHEMA.extend({
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_ON_VALUE): vol.Coerce(int),
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_OFF_VALUE): vol.Coerce(int),
    })

ISY_VARIABLES_SCHEMA = vol.Schema({
    vol.Optional(CONF_SENSORS, default=[]):
        vol.All(cv.ensure_list, [SENSOR_VAR_SCHEMA]),
    vol.Optional(CONF_BINARY_SENSORS, default=[]):
        vol.All(cv.ensure_list, [BINARY_SENSOR_VAR_SCHEMA]),
    vol.Optional(CONF_SWITCHES, default=[]):
        vol.All(cv.ensure_list, [SWITCH_VAR_SCHEMA]),
    })

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
        vol.Optional(CONF_ENABLE_CLIMATE, default=True): cv.boolean,
        vol.Optional(CONF_ISY_VARIABLES, default={}): ISY_VARIABLES_SCHEMA
    })
}, extra=vol.ALLOW_EXTRA)

WeatherNode = namedtuple('WeatherNode', ('status', 'name', 'uom'))


def _check_for_node_def(hass: HomeAssistant, node,
                        single_domain: str = None) -> bool:
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
                            single_domain: str = None) -> bool:
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

            # Hacky special-case just for FanLinc, which has a light module
            # as one of its nodes. Note that this special-case is not necessary
            # on ISY 5.x firmware as it uses the superior NodeDefs method
            if domain == 'fan' and int(node.nid[-1]) == 1:
                hass.data[ISY994_NODES]['light'].append(node)
                return True

            # Hacky special-case just for Thermostats, which has a "Heat" and
            # "Cool" sub-node on address 2 and 3
            if domain == 'climate' and int(node.nid[-1]) in [2, 3]:
                hass.data[ISY994_NODES]['binary_sensor'].append(node)
                return True

            hass.data[ISY994_NODES][domain].append(node)
            return True

    return False


def _check_for_zwave_cat(hass: HomeAssistant, node,
                         single_domain: str = None) -> bool:
    """Check if the node matches the ISY Z-Wave Category for any domains.

    This is for (presumably) every version of the ISY firmware, but only
    works for Z-Wave Devices with the devtype.cat property.
    """
    if not hasattr(node, 'devtype_cat') or node.devtype_cat is None:
        # Node doesn't have a device type category (non-Z-Wave device)
        return False

    device_type = node.devtype_cat
    domains = SUPPORTED_DOMAINS if not single_domain else [single_domain]
    for domain in domains:
        if any([device_type.startswith(t) for t in
                set(NODE_FILTERS[domain]['zwave_cat'])]):

            hass.data[ISY994_NODES][domain].append(node)
            return True

    return False


def _check_for_uom_id(hass: HomeAssistant, node,
                      single_domain: str = None,
                      uom_list: list = None) -> bool:
    """Check if a node's uom matches any of the domains uom filter.

    This is used for versions of the ISY firmware that report uoms as a single
    ID. We can often infer what type of device it is by that ID.
    """
    if not hasattr(node, 'uom') or node.uom is None:
        # Node doesn't have a uom (Scenes for example)
        return False

    node_uom = set(map(str.lower, node.uom))

    if uom_list:
        if node_uom.intersection(uom_list):
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
                             single_domain: str = None,
                             states_list: list = None) -> bool:
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
                      sensor_identifier: str) -> None:
    """Sort the nodes to their proper domains."""
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
        if _check_for_zwave_cat(hass, node):
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
                if dtype != KEY_FOLDER:
                    continue
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


def _categorize_variables(hass: HomeAssistant, variables: dict,
                          domain_cfg: dict, domain: str) -> None:
    """Categorize the ISY994 Variables."""
    if domain_cfg is None:
        return
    for isy_var in domain_cfg:
        vid = isy_var.get(CONF_ID)
        vtype = isy_var.get(CONF_TYPE)
        _, vname, _ = next((var for i, var in
                            enumerate(variables[vtype].children)
                            if var[2] == vid), None)
        if vname is None:
            _LOGGER.error("ISY Variable Not Found in ISY List; "
                          "check your config for Variable %s.%s",
                          vtype, vid)
            continue
        variable = (isy_var, vname, variables[vtype][vid])
        hass.data[ISY994_VARIABLES][domain].append(variable)


def _categorize_weather(hass: HomeAssistant, climate) -> None:
    """Categorize the ISY994 weather data."""
    climate_attrs = dir(climate)
    weather_nodes = [WeatherNode(getattr(climate, attr),
                                 attr.replace('_', ' '),
                                 getattr(climate, '{}_units'.format(attr)))
                     for attr in climate_attrs
                     if '{}_units'.format(attr) in climate_attrs]
    hass.data[ISY994_WEATHER].extend(weather_nodes)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ISY 994 platform."""
    hass.data[ISY994_NODES] = {}
    for domain in SUPPORTED_DOMAINS:
        hass.data[ISY994_NODES][domain] = []

    hass.data[ISY994_WEATHER] = []

    hass.data[ISY994_PROGRAMS] = {}
    for domain in SUPPORTED_DOMAINS:
        hass.data[ISY994_PROGRAMS][domain] = []

    hass.data[ISY994_VARIABLES] = {}
    for domain in SUPPORTED_VARIABLE_DOMAINS:
        hass.data[ISY994_VARIABLES][domain] = []

    isy_config = config.get(DOMAIN)

    user = isy_config.get(CONF_USERNAME)
    password = isy_config.get(CONF_PASSWORD)
    tls_version = isy_config.get(CONF_TLS_VER)
    host = urlparse(isy_config.get(CONF_HOST))
    ignore_identifier = isy_config.get(CONF_IGNORE_STRING)
    sensor_identifier = isy_config.get(CONF_SENSOR_STRING)
    enable_climate = isy_config.get(CONF_ENABLE_CLIMATE)
    isy_variables = isy_config.get(CONF_ISY_VARIABLES)

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
    _categorize_variables(hass, isy.variables,
                          isy_variables.get(CONF_SENSORS), 'sensor')
    _categorize_variables(hass, isy.variables,
                          isy_variables.get(CONF_BINARY_SENSORS),
                          'binary_sensor')
    _categorize_variables(hass, isy.variables,
                          isy_variables.get(CONF_SWITCHES),
                          'switch')

    if enable_climate and isy.configuration.get('Weather Information'):
        _categorize_weather(hass, isy.climate)

    async def start(event: object) -> None:
        """Start ISY auto updates."""
        _LOGGER.debug("ISY Starting Event Stream and automatic updates.")
        isy.auto_update = True

    async def stop(event: object) -> None:
        """Stop ISY auto updates."""
        isy.auto_update = False

    # only start fetching data after HA boots to prevent delaying the boot
    # process
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start)

    # Listen for HA stop to disconnect.
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop)

    # Load platforms for the devices in the ISY controller that we support.
    for component in SUPPORTED_DOMAINS:
        await discovery.async_load_platform(hass, component, DOMAIN,
                                            {}, config)

    return True


def _process_values(hass: HomeAssistant, value: str, uom: str,
                    prec: str, ntype: str) -> str:
    """Process event values to get the correct value and unit of measure."""
    if uom is None:
        return int(value)
    if isinstance(uom, list):
        uom = uom[0]  # Handle UOMs from ISYv4 firmwares
    if float(value) == -1 * float('inf'):
        return STATE_UNKNOWN
    if uom == '2':
        value = bool(int(value))
        uom = None
    elif uom == '100':
        value = int(float(value) / 255.0 * 100.0)
        uom = '%'
    elif uom == '101':
        value = round(float(value) / 2.0, 1)
        uom = hass.config.units.temperature_unit
    elif uom == '25' and ntype is not None and ntype[0] in ['1', '2']:
        # One off case for Insteon Ramp Rates
        value = INSTEON_RAMP_RATES.get(str(value), int(value))
        uom = None
    elif UOM_TO_STATES.get(uom) is not None:
        value = UOM_TO_STATES[uom].get(str(value), int(value))
        uom = None
    else:
        uom = UOM_FRIENDLY_NAME.get(uom, None)
        if prec is not None and prec != '0':
            value = round(float(value) * pow(10, -int(prec)), int(prec))
        else:
            value = int(value)
    return '{} {}'.format(value, uom) if uom is not None else value


class ISYDevice(Entity):
    """Representation of an ISY994 device."""

    _name = None  # type: str

    def __init__(self, node) -> None:
        """Initialize the insteon device."""
        self._node = node
        self._attrs = {}
        self._change_handler = None
        self._control_handler = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node change events."""
        self._change_handler = self._node.status.subscribe(
            'changed', self.on_update)

        if hasattr(self._node, 'controlEvents'):
            self._control_handler = self._node.controlEvents.subscribe(
                self.on_control)

    def on_update(self, event: object) -> None:
        """Handle the update event from the ISY994 Node."""
        self.schedule_update_ha_state()

    def on_control(self, event: object) -> None:
        """Handle a control event from the ISY994 Node."""
        event_data = {
            'entity_id': self.entity_id,
            'control': event.event,
            'value': event.nval
        }

        # Some attributes are only given by the ISY in the event stream
        # or in a direct query of a node. These are not picked up in PyISY.
        # Translate some common ones here:
        if event.nval is None or event.event not in ISY994_EVENT_IGNORE:
            attr_name = ISY994_EVENT_FRIENDLY_NAME.get(event.event,
                                                       event.event)
            friendly_value = _process_values(self.hass, event.nval,
                                             event.uom, event.prec,
                                             self._node.type)
            event_data['friendly_value'] = friendly_value
            self._attrs[attr_name] = friendly_value
            self.schedule_update_ha_state()

        self.hass.bus.fire('isy994_control', event_data)

    @property
    def unique_id(self) -> str:
        """Get the unique identifier of the device."""
        # pylint: disable=protected-access
        if hasattr(self._node, '_id'):
            return self._node._id

        return None

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
        return super().state

    @property
    def device_state_attributes(self) -> Dict:
        """Get the state attributes for the device.

        The 'aux_properties' in the PyISY Node class are combined with the
        other attributes which have been picked up from the event stream and
        the combined result are returned as the device state attributes.
        """
        attr = {}
        if hasattr(self._node, 'aux_properties'):
            for name, val in self._node.aux_properties.items():
                attr_name = ISY994_EVENT_FRIENDLY_NAME.get(name, name)
                friendly_value = _process_values(self.hass, val.get('value'),
                                                 val.get('uom', None),
                                                 val.get('prec'),
                                                 self._node.type)
                attr[attr_name] = friendly_value
        self._attrs.update(attr)
        return self._attrs
