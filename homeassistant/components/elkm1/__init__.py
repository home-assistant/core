"""Support the ElkM1 Gold and ElkM1 EZ8 alarm/integration panels."""
import asyncio
import logging
import re

import async_timeout
import elkm1_lib as elkm1
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_EXCLUDE,
    CONF_HOST,
    CONF_INCLUDE,
    CONF_PASSWORD,
    CONF_TEMPERATURE_UNIT,
    CONF_USERNAME,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_KEY,
    ATTR_KEY_NAME,
    ATTR_KEYPAD_ID,
    BARE_TEMP_CELSIUS,
    BARE_TEMP_FAHRENHEIT,
    CONF_AREA,
    CONF_AUTO_CONFIGURE,
    CONF_COUNTER,
    CONF_ENABLED,
    CONF_KEYPAD,
    CONF_OUTPUT,
    CONF_PLC,
    CONF_PREFIX,
    CONF_SETTING,
    CONF_TASK,
    CONF_THERMOSTAT,
    CONF_ZONE,
    DOMAIN,
    ELK_ELEMENTS,
    EVENT_ELKM1_KEYPAD_KEY_PRESSED,
)

SYNC_TIMEOUT = 120

_LOGGER = logging.getLogger(__name__)

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

SET_TIME_SERVICE_SCHEMA = vol.Schema(
    {
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
        vol.Optional(CONF_AUTO_CONFIGURE, default=False): cv.boolean,
        # cv.temperature_unit will mutate 'C' -> '°C' and 'F' -> '°F'
        vol.Optional(
            CONF_TEMPERATURE_UNIT, default=BARE_TEMP_FAHRENHEIT
        ): cv.temperature_unit,
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
    hass.data.setdefault(DOMAIN, {})
    _create_elk_services(hass)

    if DOMAIN not in hass_config:
        return True

    for index, conf in enumerate(hass_config[DOMAIN]):
        _LOGGER.debug("Importing elkm1 #%d - %s", index, conf[CONF_HOST])

        # The update of the config entry is done in async_setup
        # to ensure the entry if updated before async_setup_entry
        # is called to avoid a situation where the user has to restart
        # twice for the changes to take effect
        current_config_entry = _async_find_matching_config_entry(
            hass, conf[CONF_PREFIX]
        )
        if current_config_entry:
            # If they alter the yaml config we import the changes
            # since there currently is no practical way to do an options flow
            # with the large amount of include/exclude/enabled options that elkm1 has.
            hass.config_entries.async_update_entry(current_config_entry, data=conf)
            continue

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=conf,
            )
        )

    return True


@callback
def _async_find_matching_config_entry(hass, prefix):
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.unique_id == prefix:
            return entry


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Elk-M1 Control from a config entry."""

    conf = entry.data

    _LOGGER.debug("Setting up elkm1 %s", conf["host"])

    temperature_unit = TEMP_FAHRENHEIT
    if conf[CONF_TEMPERATURE_UNIT] in (BARE_TEMP_CELSIUS, TEMP_CELSIUS):
        temperature_unit = TEMP_CELSIUS

    config = {"temperature_unit": temperature_unit}

    if not conf[CONF_AUTO_CONFIGURE]:
        # With elkm1-lib==0.7.16 and later auto configure is available
        config["panel"] = {"enabled": True, "included": [True]}
        for item, max_ in ELK_ELEMENTS.items():
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

    elk = elkm1.Elk(
        {
            "url": conf[CONF_HOST],
            "userid": conf[CONF_USERNAME],
            "password": conf[CONF_PASSWORD],
        }
    )
    elk.connect()

    def _element_changed(element, changeset):
        keypress = changeset.get("last_keypress")
        if keypress is None:
            return

        hass.bus.async_fire(
            EVENT_ELKM1_KEYPAD_KEY_PRESSED,
            {
                ATTR_KEYPAD_ID: element.index + 1,
                ATTR_KEY_NAME: keypress[0],
                ATTR_KEY: keypress[1],
            },
        )

    for keypad in elk.keypads:  # pylint: disable=no-member
        keypad.add_callback(_element_changed)

    try:
        if not await async_wait_for_elk_to_sync(elk, SYNC_TIMEOUT, conf[CONF_HOST]):
            return False
    except asyncio.TimeoutError as exc:
        raise ConfigEntryNotReady from exc

    hass.data[DOMAIN][entry.entry_id] = {
        "elk": elk,
        "prefix": conf[CONF_PREFIX],
        "auto_configure": conf[CONF_AUTO_CONFIGURE],
        "config": config,
        "keypads": {},
    }

    for component in SUPPORTED_DOMAINS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


def _included(ranges, set_to, values):
    for rng in ranges:
        if not rng[0] <= rng[1] <= len(values):
            raise vol.Invalid(f"Invalid range {rng}")
        values[rng[0] - 1 : rng[1]] = [set_to] * (rng[1] - rng[0] + 1)


def _find_elk_by_prefix(hass, prefix):
    """Search all config entries for a given prefix."""
    for entry_id in hass.data[DOMAIN]:
        if hass.data[DOMAIN][entry_id]["prefix"] == prefix:
            return hass.data[DOMAIN][entry_id]["elk"]


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in SUPPORTED_DOMAINS
            ]
        )
    )

    # disconnect cleanly
    hass.data[DOMAIN][entry.entry_id]["elk"].disconnect()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_wait_for_elk_to_sync(elk, timeout, conf_host):
    """Wait until the elk has finished sync. Can fail login or timeout."""

    def login_status(succeeded):
        nonlocal success

        success = succeeded
        if succeeded:
            _LOGGER.debug("ElkM1 login succeeded")
        else:
            elk.disconnect()
            _LOGGER.error("ElkM1 login failed; invalid username or password")
            event.set()

    def sync_complete():
        event.set()

    success = True
    event = asyncio.Event()
    elk.add_handler("login", login_status)
    elk.add_handler("sync_complete", sync_complete)
    try:
        with async_timeout.timeout(timeout):
            await event.wait()
    except asyncio.TimeoutError:
        _LOGGER.error(
            "Timed out after %d seconds while trying to sync with ElkM1 at %s",
            timeout,
            conf_host,
        )
        elk.disconnect()
        raise

    return success


def _create_elk_services(hass):
    def _getelk(service):
        prefix = service.data["prefix"]
        elk = _find_elk_by_prefix(hass, prefix)
        if elk is None:
            raise HomeAssistantError(f"No ElkM1 with prefix '{prefix}' found")
        return elk

    def _speak_word_service(service):
        _getelk(service).panel.speak_word(service.data["number"])

    def _speak_phrase_service(service):
        _getelk(service).panel.speak_phrase(service.data["number"])

    def _set_time_service(service):
        _getelk(service).panel.set_time(dt_util.now())

    hass.services.async_register(
        DOMAIN, "speak_word", _speak_word_service, SPEAK_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "speak_phrase", _speak_phrase_service, SPEAK_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "set_time", _set_time_service, SET_TIME_SERVICE_SCHEMA
    )


def create_elk_entities(elk_data, elk_elements, element_type, class_, entities):
    """Create the ElkM1 devices of a particular class."""
    auto_configure = elk_data["auto_configure"]

    if not auto_configure and not elk_data["config"][element_type]["enabled"]:
        return

    elk = elk_data["elk"]
    _LOGGER.debug("Creating elk entities for %s", elk)

    for element in elk_elements:
        if auto_configure:
            if not element.configured:
                continue
        # Only check the included list if auto configure is not
        elif not elk_data["config"][element_type]["included"][element.index]:
            continue

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
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register callback for ElkM1 changes and update entity state."""
        self._element.add_callback(self._element_callback)
        self._element_callback(self._element, {})

    @property
    def device_info(self):
        """Device info connecting via the ElkM1 system."""
        return {
            "via_device": (DOMAIN, f"{self._prefix}_system"),
        }


class ElkAttachedEntity(ElkEntity):
    """An elk entity that is attached to the elk system."""

    @property
    def device_info(self):
        """Device info for the underlying ElkM1 system."""
        device_name = "ElkM1"
        if self._prefix:
            device_name += f" {self._prefix}"
        return {
            "name": device_name,
            "identifiers": {(DOMAIN, f"{self._prefix}_system")},
            "sw_version": self._elk.panel.elkm1_version,
            "manufacturer": "ELK Products, Inc.",
            "model": "M1",
        }
