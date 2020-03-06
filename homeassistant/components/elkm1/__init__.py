"""Support the ElkM1 Gold and ElkM1 EZ8 alarm/integration panels."""
import logging
import re

import elkm1_lib as elkm1
from elkm1_lib.const import Max
import voluptuous as vol

from homeassistant.const import (
    CONF_EXCLUDE,
    CONF_HOST,
    CONF_INCLUDE,
    CONF_PASSWORD,
    CONF_TEMPERATURE_UNIT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

DOMAIN = "elkm1"

CONF_AREA = "area"
CONF_COUNTER = "counter"
CONF_ENABLED = "enabled"
CONF_KEYPAD = "keypad"
CONF_OUTPUT = "output"
CONF_PLC = "plc"
CONF_SETTING = "setting"
CONF_TASK = "task"
CONF_THERMOSTAT = "thermostat"
CONF_ZONE = "zone"
CONF_PREFIX = "prefix"

_LOGGER = logging.getLogger(__name__)

SERVICE_ALARM_DISPLAY_MESSAGE = "alarm_display_message"
SERVICE_ALARM_ARM_VACATION = "alarm_arm_vacation"
SERVICE_ALARM_ARM_HOME_INSTANT = "alarm_arm_home_instant"
SERVICE_ALARM_ARM_NIGHT_INSTANT = "alarm_arm_night_instant"

SUPPORTED_DOMAINS = [
    "alarm_control_panel",
    "climate",
    "light",
    "scene",
    "sensor",
    "switch",
]

SPEAK_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("number"): vol.All(vol.Coerce(int), vol.Range(min=0, max=999)),
        vol.Optional("prefix", default=""): cv.string,
    }
)


def _host_validator(config):
    """Validate that a host is properly configured."""
    if config[CONF_HOST].startswith("elks://"):
        if CONF_USERNAME not in config or CONF_PASSWORD not in config:
            raise vol.Invalid("Specify username and password for elks://")
    elif not config[CONF_HOST].startswith("elk://") and not config[
        CONF_HOST
    ].startswith("serial://"):
        raise vol.Invalid("Invalid host URL")
    return config


def _elk_range_validator(rng):
    def _housecode_to_int(val):
        match = re.search(r"^([a-p])(0[1-9]|1[0-6]|[1-9])$", val.lower())
        if match:
            return (ord(match.group(1)) - ord("a")) * 16 + int(match.group(2))
        raise vol.Invalid("Invalid range")

    def _elk_value(val):
        return int(val) if val.isdigit() else _housecode_to_int(val)

    vals = [s.strip() for s in str(rng).split("-")]
    start = _elk_value(vals[0])
    end = start if len(vals) == 1 else _elk_value(vals[1])
    return (start, end)


def _has_all_unique_prefixes(value):
    """Validate that each m1 configured has a unique prefix.

    Uniqueness is determined case-independently.
    """
    prefixes = [device[CONF_PREFIX] for device in value]
    schema = vol.Schema(vol.Unique())
    schema(prefixes)
    return value


DEVICE_SCHEMA_SUBDOMAIN = vol.Schema(
    {
        vol.Optional(CONF_ENABLED, default=True): cv.boolean,
        vol.Optional(CONF_INCLUDE, default=[]): [_elk_range_validator],
        vol.Optional(CONF_EXCLUDE, default=[]): [_elk_range_validator],
    }
)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PREFIX, default=""): vol.All(cv.string, vol.Lower),
        vol.Optional(CONF_USERNAME, default=""): cv.string,
        vol.Optional(CONF_PASSWORD, default=""): cv.string,
        vol.Optional(CONF_TEMPERATURE_UNIT, default="F"): cv.temperature_unit,
        vol.Optional(CONF_AREA, default={}): DEVICE_SCHEMA_SUBDOMAIN,
        vol.Optional(CONF_COUNTER, default={}): DEVICE_SCHEMA_SUBDOMAIN,
        vol.Optional(CONF_KEYPAD, default={}): DEVICE_SCHEMA_SUBDOMAIN,
        vol.Optional(CONF_OUTPUT, default={}): DEVICE_SCHEMA_SUBDOMAIN,
        vol.Optional(CONF_PLC, default={}): DEVICE_SCHEMA_SUBDOMAIN,
        vol.Optional(CONF_SETTING, default={}): DEVICE_SCHEMA_SUBDOMAIN,
        vol.Optional(CONF_TASK, default={}): DEVICE_SCHEMA_SUBDOMAIN,
        vol.Optional(CONF_THERMOSTAT, default={}): DEVICE_SCHEMA_SUBDOMAIN,
        vol.Optional(CONF_ZONE, default={}): DEVICE_SCHEMA_SUBDOMAIN,
    },
    _host_validator,
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [DEVICE_SCHEMA], _has_all_unique_prefixes)},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, hass_config: ConfigType) -> bool:
    """Set up the Elk M1 platform."""
    devices = {}
    elk_datas = {}

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
                raise vol.Invalid(f"Invalid range {rng}")
            values[rng[0] - 1 : rng[1]] = [set_to] * (rng[1] - rng[0] + 1)

    for index, conf in enumerate(hass_config[DOMAIN]):
        _LOGGER.debug("Setting up elkm1 #%d - %s", index, conf["host"])

        config = {"temperature_unit": conf[CONF_TEMPERATURE_UNIT]}
        config["panel"] = {"enabled": True, "included": [True]}

        for item, max_ in configs.items():
            config[item] = {
                "enabled": conf[item][CONF_ENABLED],
                "included": [not conf[item]["include"]] * max_,
            }
            try:
                _included(conf[item]["include"], True, config[item]["included"])
                _included(conf[item]["exclude"], False, config[item]["included"])
            except (ValueError, vol.Invalid) as err:
                _LOGGER.error("Config item: %s; %s", item, err)
                return False

        prefix = conf[CONF_PREFIX]
        elk = elkm1.Elk(
            {
                "url": conf[CONF_HOST],
                "userid": conf[CONF_USERNAME],
                "password": conf[CONF_PASSWORD],
            }
        )
        elk.connect()

        devices[prefix] = elk
        elk_datas[prefix] = {
            "elk": elk,
            "prefix": prefix,
            "config": config,
            "keypads": {},
        }

    _create_elk_services(hass, devices)

    hass.data[DOMAIN] = elk_datas
    for component in SUPPORTED_DOMAINS:
        hass.async_create_task(
            discovery.async_load_platform(hass, component, DOMAIN, {}, hass_config)
        )

    return True


def _create_elk_services(hass, elks):
    def _speak_word_service(service):
        prefix = service.data["prefix"]
        elk = elks.get(prefix)
        if elk is None:
            _LOGGER.error("No elk m1 with prefix for speak_word: '%s'", prefix)
            return
        elk.panel.speak_word(service.data["number"])

    def _speak_phrase_service(service):
        prefix = service.data["prefix"]
        elk = elks.get(prefix)
        if elk is None:
            _LOGGER.error("No elk m1 with prefix for speak_phrase: '%s'", prefix)
            return
        elk.panel.speak_phrase(service.data["number"])

    hass.services.async_register(
        DOMAIN, "speak_word", _speak_word_service, SPEAK_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "speak_phrase", _speak_phrase_service, SPEAK_SERVICE_SCHEMA
    )


def create_elk_entities(elk_data, elk_elements, element_type, class_, entities):
    """Create the ElkM1 devices of a particular class."""
    if elk_data["config"][element_type]["enabled"]:
        elk = elk_data["elk"]
        _LOGGER.debug("Creating elk entities for %s", elk)
        for element in elk_elements:
            if elk_data["config"][element_type]["included"][element.index]:
                entities.append(class_(element, elk, elk_data))
    return entities


class ElkEntity(Entity):
    """Base class for all Elk entities."""

    def __init__(self, element, elk, elk_data):
        """Initialize the base of all Elk devices."""
        self._elk = elk
        self._element = element
        self._prefix = elk_data["prefix"]
        self._temperature_unit = elk_data["config"]["temperature_unit"]
        # unique_id starts with elkm1_ iff there is no prefix
        # it starts with elkm1m_{prefix} iff there is a prefix
        # this is to avoid a conflict between
        # prefix=foo, name=bar  (which would be elkm1_foo_bar)
        #   - and -
        # prefix="", name="foo bar" (which would be elkm1_foo_bar also)
        # we could have used elkm1__foo_bar for the latter, but that
        # would have been a breaking change
        if self._prefix != "":
            uid_start = f"elkm1m_{self._prefix}"
        else:
            uid_start = "elkm1"
        self._unique_id = f"{uid_start}_{self._element.default_name('_')}".lower()

    @property
    def name(self):
        """Name of the element."""
        return f"{self._prefix}{self._element.name}"

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
        attrs["index"] = self._element.index + 1
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
