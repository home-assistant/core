"""Support the ElkM1 Gold and ElkM1 EZ8 alarm/integration panels."""
import logging
import re

import voluptuous as vol
from homeassistant.const import (
    CONF_EXCLUDE, CONF_HOST, CONF_INCLUDE, CONF_PASSWORD,
    CONF_TEMPERATURE_UNIT, CONF_USERNAME)
from homeassistant.core import HomeAssistant, callback  # noqa
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType  # noqa

REQUIREMENTS = ['elkm1-lib==0.7.13']

DOMAIN = 'elkm1'

CONF_AREA = 'area'
CONF_COUNTER = 'counter'
CONF_ENABLED = 'enabled'
CONF_KEYPAD = 'keypad'
CONF_OUTPUT = 'output'
CONF_PLC = 'plc'
CONF_SETTING = 'setting'
CONF_TASK = 'task'
CONF_THERMOSTAT = 'thermostat'
CONF_ZONE = 'zone'

_LOGGER = logging.getLogger(__name__)

SUPPORTED_DOMAINS = ['alarm_control_panel', 'climate', 'light', 'scene',
                     'sensor', 'switch']

SPEAK_SERVICE_SCHEMA = vol.Schema({
    vol.Required('number'):
        vol.All(vol.Coerce(int), vol.Range(min=0, max=999))
})


def _host_validator(config):
    """Validate that a host is properly configured."""
    if config[CONF_HOST].startswith('elks://'):
        if CONF_USERNAME not in config or CONF_PASSWORD not in config:
            raise vol.Invalid("Specify username and password for elks://")
    elif not config[CONF_HOST].startswith('elk://') and not config[
            CONF_HOST].startswith('serial://'):
        raise vol.Invalid("Invalid host URL")
    return config


def _elk_range_validator(rng):
    def _housecode_to_int(val):
        match = re.search(r'^([a-p])(0[1-9]|1[0-6]|[1-9])$', val.lower())
        if match:
            return (ord(match.group(1)) - ord('a')) * 16 + int(match.group(2))
        raise vol.Invalid("Invalid range")

    def _elk_value(val):
        return int(val) if val.isdigit() else _housecode_to_int(val)

    vals = [s.strip() for s in str(rng).split('-')]
    start = _elk_value(vals[0])
    end = start if len(vals) == 1 else _elk_value(vals[1])
    return (start, end)


CONFIG_SCHEMA_SUBDOMAIN = vol.Schema({
    vol.Optional(CONF_ENABLED, default=True): cv.boolean,
    vol.Optional(CONF_INCLUDE, default=[]): [_elk_range_validator],
    vol.Optional(CONF_EXCLUDE, default=[]): [_elk_range_validator],
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_USERNAME, default=''): cv.string,
            vol.Optional(CONF_PASSWORD, default=''): cv.string,
            vol.Optional(CONF_TEMPERATURE_UNIT, default='F'):
                cv.temperature_unit,
            vol.Optional(CONF_AREA, default={}): CONFIG_SCHEMA_SUBDOMAIN,
            vol.Optional(CONF_COUNTER, default={}): CONFIG_SCHEMA_SUBDOMAIN,
            vol.Optional(CONF_KEYPAD, default={}): CONFIG_SCHEMA_SUBDOMAIN,
            vol.Optional(CONF_OUTPUT, default={}): CONFIG_SCHEMA_SUBDOMAIN,
            vol.Optional(CONF_PLC, default={}): CONFIG_SCHEMA_SUBDOMAIN,
            vol.Optional(CONF_SETTING, default={}): CONFIG_SCHEMA_SUBDOMAIN,
            vol.Optional(CONF_TASK, default={}): CONFIG_SCHEMA_SUBDOMAIN,
            vol.Optional(CONF_THERMOSTAT, default={}): CONFIG_SCHEMA_SUBDOMAIN,
            vol.Optional(CONF_ZONE, default={}): CONFIG_SCHEMA_SUBDOMAIN,
        },
        _host_validator,
    )
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, hass_config: ConfigType) -> bool:
    """Set up the Elk M1 platform."""
    from elkm1_lib.const import Max
    import elkm1_lib as elkm1

    configs = {
        CONF_AREA: Max.AREAS.value,
        CONF_COUNTER: Max.COUNTERS.value,
        CONF_KEYPAD: Max.KEYPADS.value,
        CONF_OUTPUT: Max.OUTPUTS.value,
        CONF_PLC: Max.LIGHTS.value,
        CONF_SETTING: Max.SETTINGS.value,
        CONF_TASK: Max.TASKS.value,
        CONF_THERMOSTAT: Max.THERMOSTATS.value,
        CONF_ZONE: Max.ZONES.value,
    }

    def _included(ranges, set_to, values):
        for rng in ranges:
            if not rng[0] <= rng[1] <= len(values):
                raise vol.Invalid("Invalid range {}".format(rng))
            values[rng[0]-1:rng[1]] = [set_to] * (rng[1] - rng[0] + 1)

    conf = hass_config[DOMAIN]
    config = {'temperature_unit': conf[CONF_TEMPERATURE_UNIT]}
    config['panel'] = {'enabled': True, 'included': [True]}

    for item, max_ in configs.items():
        config[item] = {'enabled': conf[item][CONF_ENABLED],
                        'included': [not conf[item]['include']] * max_}
        try:
            _included(conf[item]['include'], True, config[item]['included'])
            _included(conf[item]['exclude'], False, config[item]['included'])
        except (ValueError, vol.Invalid) as err:
            _LOGGER.error("Config item: %s; %s", item, err)
            return False

    elk = elkm1.Elk({'url': conf[CONF_HOST], 'userid': conf[CONF_USERNAME],
                     'password': conf[CONF_PASSWORD]})
    elk.connect()

    _create_elk_services(hass, elk)

    hass.data[DOMAIN] = {'elk': elk, 'config': config, 'keypads': {}}
    for component in SUPPORTED_DOMAINS:
        hass.async_create_task(
            discovery.async_load_platform(hass, component, DOMAIN, {},
                                          hass_config))

    return True


def _create_elk_services(hass, elk):
    def _speak_word_service(service):
        elk.panel.speak_word(service.data.get('number'))

    def _speak_phrase_service(service):
        elk.panel.speak_phrase(service.data.get('number'))

    hass.services.async_register(
        DOMAIN, 'speak_word', _speak_word_service, SPEAK_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, 'speak_phrase', _speak_phrase_service, SPEAK_SERVICE_SCHEMA)


def create_elk_entities(hass, elk_elements, element_type, class_, entities):
    """Create the ElkM1 devices of a particular class."""
    elk_data = hass.data[DOMAIN]
    if elk_data['config'][element_type]['enabled']:
        elk = elk_data['elk']
        for element in elk_elements:
            if elk_data['config'][element_type]['included'][element.index]:
                entities.append(class_(element, elk, elk_data))
    return entities


class ElkEntity(Entity):
    """Base class for all Elk entities."""

    def __init__(self, element, elk, elk_data):
        """Initialize the base of all Elk devices."""
        self._elk = elk
        self._element = element
        self._temperature_unit = elk_data['config']['temperature_unit']
        self._unique_id = 'elkm1_{}'.format(
            self._element.default_name('_').lower())

    @property
    def name(self):
        """Name of the element."""
        return self._element.name

    @property
    def unique_id(self):
        """Return unique id of the element."""
        return self._unique_id

    @property
    def should_poll(self) -> bool:
        """Don't poll this device."""
        return False

    @property
    def device_state_attributes(self):
        """Return the default attributes of the element."""
        return {**self._element.as_dict(), **self.initial_attrs()}

    @property
    def available(self):
        """Is the entity available to be updated."""
        return self._elk.is_connected()

    def initial_attrs(self):
        """Return the underlying element's attributes as a dict."""
        attrs = {}
        attrs['index'] = self._element.index + 1
        return attrs

    def _element_changed(self, element, changeset):
        pass

    @callback
    def _element_callback(self, element, changeset):
        """Handle callback from an Elk element that has changed."""
        self._element_changed(element, changeset)
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Register callback for ElkM1 changes and update entity state."""
        self._element.add_callback(self._element_callback)
        self._element_callback(self._element, {})
