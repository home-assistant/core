"""
Support the ElkM1 Gold and ElkM1 EZ8 alarm / integration panels.

Uses https://pypi.org/project/elkm1-lib/

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/elkm1/
"""

import logging

import voluptuous as vol
from homeassistant.const import (
    CONF_EXCLUDE, CONF_HOST, CONF_INCLUDE, CONF_PASSWORD,
    CONF_TEMPERATURE_UNIT, CONF_USERNAME, TEMP_FAHRENHEIT)
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
CONF_PLC = 'plc'
CONF_ZONE = 'zone'

CONF_ENABLED = 'enabled'
CONF_HIDE = 'hide'
CONF_SHOW = 'show'

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA_SUBDOMAIN = vol.Schema({
    vol.Optional(CONF_ENABLED, default=True): cv.boolean,
    vol.Optional(CONF_INCLUDE): list,
    vol.Optional(CONF_EXCLUDE): list
    })

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TEMPERATURE_UNIT, default=TEMP_FAHRENHEIT):
            cv.temperature_unit,
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

SUPPORTED_DOMAINS = ['alarm_control_panel']


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
            raise vol.Invalid('Value not in range 1-%d: "%s"' % (max_, val))
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
            return (True, [True] * max_)

        conf = config_raw[item]

        if CONF_ENABLED in conf and not conf[CONF_ENABLED]:
            return (False, [False] * max_)

        included = [CONF_INCLUDE not in conf] * max_
        parse_range(conf, CONF_INCLUDE, True, included, max_)
        parse_range(conf, CONF_EXCLUDE, False, included, max_)

        return (True, included)

    config_raw = hass_config.get(DOMAIN)
    config = {}

    host = config_raw[CONF_HOST]
    username = config_raw.get(CONF_USERNAME)
    password = config_raw.get(CONF_PASSWORD)
    if host.startswith('elks:') and (username is None or password is None):
        raise vol.Invalid("Specify username & password for elks://")

    for item, max_ in configs.items():
        config[item] = {}
        (config[item]['enabled'], config[item]['included']) = \
            parse_config(item, max_)

    config['temperature_unit'] = config_raw[CONF_TEMPERATURE_UNIT]

    elk = elkm1.Elk({'url': host, 'userid': username, 'password': password})
    elk.connect()

    hass.data[DOMAIN] = {'elk': elk, 'config': config,
                         'entities': {}, 'keypads': {}}
    for component in SUPPORTED_DOMAINS:
        hass.async_create_task(
            discovery.async_load_platform(hass, component, DOMAIN))
    return True


def create_elk_entities(hass, elk_elements, element_type, class_, entities):
    """Helper to create the ElkM1 devices of a particular class."""
    elk_data = hass.data[DOMAIN]
    elk = elk_data['elk']
    for element in elk_elements:
        if elk_data['config'][element_type]['included'][element.index]:
            entities.append(class_(element, elk, elk_data))
    return entities


class ElkDeviceBase(Entity):
    """Sensor devices on the Elk."""
    def __init__(self, platform, element, elk, elk_data):
        self._elk = elk
        self._element = element
        self._state = None
        self._temperature_unit = elk_data['config']['temperature_unit']
        self._unique_id = 'elkm1_{}'.format(
            self._element.default_name('_').lower())

    @property
    def name(self):
        """Name of the element."""
        return self._element.name

    @property
    def unique_id(self):
        """Unique id of the element."""
        return self._unique_id

    @property
    def should_poll(self) -> bool:
        """Don't poll this device."""
        return False

    @property
    def device_state_attributes(self):
        """Default attributes of the element, if not overridden."""
        return {**self._element.as_dict(), **self.initial_attrs()}

    @property
    def available(self):
        """Is the entity available to be updated."""
        return self._elk.is_connected()

    def initial_attrs(self):
        """The underlying element's attributes as a dict."""
        attrs = {}
        attrs['index'] = self._element.index + 1
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
