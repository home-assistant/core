"""
Support the ElkM1 Gold and ElkM1 EZ8 alarm / integration panels.

Uses https://pypi.org/project/elkm1-lib/

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/elkm1/
"""

import logging

import voluptuous as vol
from homeassistant.const import (ATTR_ENTITY_ID, CONF_EXCLUDE,
                                 CONF_HOST, CONF_INCLUDE, CONF_PASSWORD,
                                 CONF_TEMPERATURE_UNIT, CONF_USERNAME,
                                 STATE_UNKNOWN, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.core import HomeAssistant, callback  # noqa
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType  # noqa

DOMAIN = "elkm1"

REQUIREMENTS = ['elkm1-lib==0.7.10']

CONF_AREA = 'area'
CONF_COUNTER = 'counter'
CONF_KEYPAD = 'keypad'
CONF_OUTPUT = 'output'
CONF_SETTING = 'setting'
CONF_TASK = 'task'
CONF_THERMOSTAT = 'thermostat'
CONF_USER = 'user'
CONF_PANEL = 'panel'
CONF_PLC = 'plc'  # Not light because HASS complains about this
CONF_ZONE = 'zone'

CONF_ENABLED = 'enabled'    # True to enable subdomain
CONF_HIDE = 'hide'
CONF_SHOW = 'show'

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA_SUBDOMAIN = vol.Schema({
    vol.Optional(CONF_ENABLED, default=True): cv.boolean,
    vol.Optional(CONF_INCLUDE): list,
    vol.Optional(CONF_EXCLUDE): list,
    vol.Optional(CONF_HIDE): list,
    vol.Optional(CONF_SHOW): list,
    })

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TEMPERATURE_UNIT, default='fahrenheit'):
            vol.In(['celsius', 'fahrenheit']),
        vol.Optional(CONF_AREA): CONFIG_SCHEMA_SUBDOMAIN,
        vol.Optional(CONF_COUNTER): CONFIG_SCHEMA_SUBDOMAIN,
        vol.Optional(CONF_KEYPAD): CONFIG_SCHEMA_SUBDOMAIN,
        vol.Optional(CONF_OUTPUT): CONFIG_SCHEMA_SUBDOMAIN,
        vol.Optional(CONF_PLC): CONFIG_SCHEMA_SUBDOMAIN,
        vol.Optional(CONF_SETTING): CONFIG_SCHEMA_SUBDOMAIN,
        vol.Optional(CONF_TASK): CONFIG_SCHEMA_SUBDOMAIN,
        vol.Optional(CONF_THERMOSTAT): CONFIG_SCHEMA_SUBDOMAIN,
        vol.Optional(CONF_USER): CONFIG_SCHEMA_SUBDOMAIN,
        vol.Optional(CONF_ZONE): CONFIG_SCHEMA_SUBDOMAIN,
    })
}, extra=vol.ALLOW_EXTRA)

SUPPORTED_DOMAINS = ['sensor', 'switch', 'alarm_control_panel',
                     'climate', 'light']


async def async_setup(hass: HomeAssistant, hass_config: ConfigType) -> bool:
    """Set up the Elk M1 platform."""

    from elkm1_lib.const import Max
    from elkm1_lib.message import housecode_to_index
    import elkm1_lib as elkm1

    configs = {
        CONF_AREA: Max.AREAS.value,
        CONF_COUNTER: Max.COUNTERS.value,
        CONF_KEYPAD: Max.KEYPADS.value,
        CONF_OUTPUT: Max.OUTPUTS.value,
        CONF_PANEL: 1,
        CONF_PLC: Max.LIGHTS.value,
        CONF_SETTING: Max.SETTINGS.value,
        CONF_TASK: Max.TASKS.value,
        CONF_THERMOSTAT: Max.THERMOSTATS.value,
        CONF_USER: Max.USERS.value,
        CONF_ZONE: Max.ZONES.value,
    }

    def parse_value(val, max_):
        """Parse a value as an int or housecode."""
        i = int(val) if val.isdigit() else (housecode_to_index(val) + 1)
        if i < 1 or i > max_:
            raise ValueError('Value not in range 1 to %d: "%s"' % (max_, val))
        return i

    def parse_range(config, item, set_to, values, max_):
        """Parse a range list, e.g. range in form of 3 or 2-7"""
        ranges = config.get(item, [])
        for rng in ranges:
            rng = str(rng)
            if '-' in rng:
                rng_vals = [s.strip() for s in rng.split('-')]
                start = parse_value(rng_vals[0], max_)
                end = parse_value(rng_vals[1], max_)
            else:
                start = end = parse_value(rng, max_)
            values[start-1:end] = [set_to] * (end - start + 1)

    def parse_config(item, max_):
        """Parse a config for an element type such as: zones, plc, etc."""
        if item not in config_raw:
            return (True, [True] * max_, [True] * max_)

        conf = config_raw[item]

        if CONF_ENABLED in conf and not conf[CONF_ENABLED]:
            return (False, [False] * max_, [False] * max_)

        included = [CONF_INCLUDE not in conf] * max_
        parse_range(conf, CONF_INCLUDE, True, included, max_)
        parse_range(conf, CONF_EXCLUDE, False, included, max_)

        shown = [None] * max_
        parse_range(conf, CONF_SHOW, True, shown, max_)
        parse_range(conf, CONF_HIDE, False, shown, max_)

        return (True, included, shown)

    config_raw = hass_config.get(DOMAIN)
    config = {}

    host = config_raw[CONF_HOST]
    username = config_raw.get(CONF_USERNAME)
    password = config_raw.get(CONF_PASSWORD)
    if host.startswith('elks:'):
        if username is None or password is None:
            _LOGGER.error('Specify username & password for secure connection')
            return False

    for item, max_ in configs.items():
        config[item] = {}
        try:
            (config[item]['enabled'], config[item]['included'],
             config[item]['shown']) = parse_config(item, max_)
        except ValueError as err:
            _LOGGER.error("Config item: %s; %s", item, err)
            return False

    config['temperature_unit'] = config_raw[CONF_TEMPERATURE_UNIT]

    elk = elkm1.Elk({'url': host, 'userid': username, 'password': password})
    elk.connect()

    hass.data[DOMAIN] = {'elk': elk, 'config': config,
                         'entities': {}, 'keypads': {}}
    for component in SUPPORTED_DOMAINS:
        hass.async_add_job(
            discovery.async_load_platform(hass, component, DOMAIN, None, None))
    return True


def create_elk_devices(hass, elk_elements, element_type, class_, devices):
    """Helper to create the ElkM1 devices of a particular class."""
    config = hass.data[DOMAIN]['config']
    for element in elk_elements:
        if config[element_type]['included'][element.index]:
            devices.append(class_(element, hass, config[element_type]))
    return devices


def register_elk_service(hass, domain, service_name, schema, service_handler):
    """Map services to methods."""
    async def async_service_handler(service):
        for entity_id in service.data.get(ATTR_ENTITY_ID, []):
            entity = hass.data[DOMAIN]['entities'].get(entity_id)
            if not entity:
                continue

            handler = getattr(entity, service_handler)
            if not handler:
                continue

            kwargs = {key: val for key, val in service.data.items()
                      if key != ATTR_ENTITY_ID}
            await handler(**kwargs)

    hass.services.async_register(
        domain, service_name, async_service_handler, schema=schema)


class ElkDeviceBase(Entity):
    """Sensor devices on the Elk."""
    def __init__(self, platform, element, hass, config):
        self._elk = hass.data[DOMAIN]['elk']
        self._element = element
        self._hass = hass
        self._show_override = config['shown'][element.index]
        self._hidden = False
        self._state = STATE_UNKNOWN
        self._temperature_unit = TEMP_CELSIUS if hass.data[DOMAIN][
            'config']['temperature_unit'] == 'celsius' else TEMP_FAHRENHEIT
        self._unique_id = platform + '.elkm1_' + \
            self._element.default_name('_').lower()
        self.entity_id = self._unique_id

    @property
    def name(self):
        """Name of the element."""
        return self._element.name

    @property
    def unique_id(self):
        """Unique id of the element."""
        return self._unique_id

    @property
    def state(self):
        """The state of the element."""
        return self._state

    @property
    def should_poll(self) -> bool:
        """Don't poll this device."""
        return False

    @property
    def hidden(self):
        """Return if the element is hidden."""
        if self._show_override is None:
            return self._hidden
        return not self._show_override

    @property
    def device_state_attributes(self):
        """Default attributes of the element, if not overridden."""
        return {**self._element.as_dict(), **self.initial_attrs()}

    def initial_attrs(self):
        """The underlying element's attributes as a dict."""
        attrs = {}
        attrs['index'] = self._element.index + 1
        attrs['state'] = self._state
        return attrs

    def _element_changed(self, element, changeset):
        raise NotImplementedError()

    @callback
    def _element_callback(self, element, changeset):
        """Callback handler from the Elk - required to be supplied."""
        self._element_changed(element, changeset)
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Register callback for ElkM1 changes and update entity state."""
        self._element.add_callback(self._element_callback)
        self._element_callback(self._element, {})
        self._hass.data[DOMAIN]['entities'][self.entity_id] = self
