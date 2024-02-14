"""Support the ElkM1 Gold and ElkM1 EZ8 alarm/integration panels."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from enum import Enum
import logging
import re
from types import MappingProxyType
from typing import Any

from elkm1_lib.elements import Element
from elkm1_lib.elk import Elk
from elkm1_lib.util import parse_url
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_CONNECTIONS,
    CONF_ENABLED,
    CONF_EXCLUDE,
    CONF_HOST,
    CONF_INCLUDE,
    CONF_PASSWORD,
    CONF_PREFIX,
    CONF_TEMPERATURE_UNIT,
    CONF_USERNAME,
    CONF_ZONE,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util
from homeassistant.util.network import is_ip_address

from .const import (
    ATTR_KEY,
    ATTR_KEY_NAME,
    ATTR_KEYPAD_ID,
    ATTR_KEYPAD_NAME,
    CONF_AREA,
    CONF_AUTO_CONFIGURE,
    CONF_COUNTER,
    CONF_KEYPAD,
    CONF_OUTPUT,
    CONF_PLC,
    CONF_SETTING,
    CONF_TASK,
    CONF_THERMOSTAT,
    DISCOVER_SCAN_TIMEOUT,
    DISCOVERY_INTERVAL,
    DOMAIN,
    ELK_ELEMENTS,
    EVENT_ELKM1_KEYPAD_KEY_PRESSED,
    LOGIN_TIMEOUT,
)
from .discovery import (
    async_discover_device,
    async_discover_devices,
    async_trigger_discovery,
    async_update_entry_from_discovery,
)
from .models import ELKM1Data

SYNC_TIMEOUT = 120

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.SCENE,
    Platform.SENSOR,
    Platform.SWITCH,
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


def hostname_from_url(url: str) -> str:
    """Return the hostname from a url."""
    return parse_url(url)[1]


def _host_validator(config: dict[str, str]) -> dict[str, str]:
    """Validate that a host is properly configured."""
    if config[CONF_HOST].startswith("elks://"):
        if CONF_USERNAME not in config or CONF_PASSWORD not in config:
            raise vol.Invalid("Specify username and password for elks://")
    elif not config[CONF_HOST].startswith("elk://") and not config[
        CONF_HOST
    ].startswith("serial://"):
        raise vol.Invalid("Invalid host URL")
    return config


def _elk_range_validator(rng: str) -> tuple[int, int]:
    def _housecode_to_int(val: str) -> int:
        match = re.search(r"^([a-p])(0[1-9]|1[0-6]|[1-9])$", val.lower())
        if match:
            return (ord(match.group(1)) - ord("a")) * 16 + int(match.group(2))
        raise vol.Invalid("Invalid range")

    def _elk_value(val: str) -> int:
        return int(val) if val.isdigit() else _housecode_to_int(val)

    vals = [s.strip() for s in str(rng).split("-")]
    start = _elk_value(vals[0])
    end = start if len(vals) == 1 else _elk_value(vals[1])
    return (start, end)


def _has_all_unique_prefixes(value: list[dict[str, str]]) -> list[dict[str, str]]:
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

DEVICE_SCHEMA = vol.All(
    cv.deprecated(CONF_TEMPERATURE_UNIT),
    vol.Schema(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_PREFIX, default=""): vol.All(cv.string, vol.Lower),
            vol.Optional(CONF_USERNAME, default=""): cv.string,
            vol.Optional(CONF_PASSWORD, default=""): cv.string,
            vol.Optional(CONF_AUTO_CONFIGURE, default=False): cv.boolean,
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
    ),
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [DEVICE_SCHEMA], _has_all_unique_prefixes)},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, hass_config: ConfigType) -> bool:
    """Set up the Elk M1 platform."""
    hass.data.setdefault(DOMAIN, {})
    _create_elk_services(hass)

    async def _async_discovery(*_: Any) -> None:
        async_trigger_discovery(
            hass, await async_discover_devices(hass, DISCOVER_SCAN_TIMEOUT)
        )

    hass.async_create_background_task(_async_discovery(), "elkm1 setup discovery")
    async_track_time_interval(
        hass, _async_discovery, DISCOVERY_INTERVAL, cancel_on_shutdown=True
    )

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
def _async_find_matching_config_entry(
    hass: HomeAssistant, prefix: str
) -> ConfigEntry | None:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.unique_id == prefix:
            return entry
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elk-M1 Control from a config entry."""
    conf: MappingProxyType[str, Any] = entry.data

    host = hostname_from_url(entry.data[CONF_HOST])

    _LOGGER.debug("Setting up elkm1 %s", conf["host"])

    if (not entry.unique_id or ":" not in entry.unique_id) and is_ip_address(host):
        _LOGGER.debug(
            "Unique id for %s is missing during setup, trying to fill from discovery",
            host,
        )
        if device := await async_discover_device(hass, host):
            async_update_entry_from_discovery(hass, entry, device)

    config: dict[str, Any] = {}

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

    elk = Elk(
        {
            "url": conf[CONF_HOST],
            "userid": conf[CONF_USERNAME],
            "password": conf[CONF_PASSWORD],
        }
    )
    elk.connect()

    def _keypad_changed(keypad: Element, changeset: dict[str, Any]) -> None:
        if (keypress := changeset.get("last_keypress")) is None:
            return

        hass.bus.async_fire(
            EVENT_ELKM1_KEYPAD_KEY_PRESSED,
            {
                ATTR_KEYPAD_NAME: keypad.name,
                ATTR_KEYPAD_ID: keypad.index + 1,
                ATTR_KEY_NAME: keypress[0],
                ATTR_KEY: keypress[1],
            },
        )

    for keypad in elk.keypads:
        keypad.add_callback(_keypad_changed)

    try:
        if not await async_wait_for_elk_to_sync(elk, LOGIN_TIMEOUT, SYNC_TIMEOUT):
            return False
    except TimeoutError as exc:
        raise ConfigEntryNotReady(f"Timed out connecting to {conf[CONF_HOST]}") from exc

    elk_temp_unit = elk.panel.temperature_units
    if elk_temp_unit == "C":
        temperature_unit = UnitOfTemperature.CELSIUS
    else:
        temperature_unit = UnitOfTemperature.FAHRENHEIT
    config["temperature_unit"] = temperature_unit
    prefix: str = conf[CONF_PREFIX]
    auto_configure: bool = conf[CONF_AUTO_CONFIGURE]
    hass.data[DOMAIN][entry.entry_id] = ELKM1Data(
        elk=elk,
        prefix=prefix,
        mac=entry.unique_id,
        auto_configure=auto_configure,
        config=config,
        keypads={},
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _included(ranges: list[tuple[int, int]], set_to: bool, values: list[bool]) -> None:
    for rng in ranges:
        if not rng[0] <= rng[1] <= len(values):
            raise vol.Invalid(f"Invalid range {rng}")
        values[rng[0] - 1 : rng[1]] = [set_to] * (rng[1] - rng[0] + 1)


def _find_elk_by_prefix(hass: HomeAssistant, prefix: str) -> Elk | None:
    """Search all config entries for a given prefix."""
    all_elk: dict[str, ELKM1Data] = hass.data[DOMAIN]
    for elk_data in all_elk.values():
        if elk_data.prefix == prefix:
            return elk_data.elk
    return None


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    all_elk: dict[str, ELKM1Data] = hass.data[DOMAIN]

    # disconnect cleanly
    all_elk[entry.entry_id].elk.disconnect()

    if unload_ok:
        all_elk.pop(entry.entry_id)

    return unload_ok


async def async_wait_for_elk_to_sync(
    elk: Elk,
    login_timeout: int,
    sync_timeout: int,
) -> bool:
    """Wait until the elk has finished sync. Can fail login or timeout."""

    sync_event = asyncio.Event()
    login_event = asyncio.Event()

    success = True

    def login_status(succeeded: bool) -> None:
        nonlocal success

        success = succeeded
        if succeeded:
            _LOGGER.debug("ElkM1 login succeeded")
            login_event.set()
        else:
            elk.disconnect()
            _LOGGER.error("ElkM1 login failed; invalid username or password")
            login_event.set()
            sync_event.set()

    def sync_complete() -> None:
        sync_event.set()

    elk.add_handler("login", login_status)
    elk.add_handler("sync_complete", sync_complete)
    for name, event, timeout in (
        ("login", login_event, login_timeout),
        ("sync_complete", sync_event, sync_timeout),
    ):
        _LOGGER.debug("Waiting for %s event for %s seconds", name, timeout)
        try:
            async with asyncio.timeout(timeout):
                await event.wait()
        except TimeoutError:
            _LOGGER.debug("Timed out waiting for %s event", name)
            elk.disconnect()
            raise
        _LOGGER.debug("Received %s event", name)

    return success


def _create_elk_services(hass: HomeAssistant) -> None:
    def _getelk(service: ServiceCall) -> Elk:
        prefix = service.data["prefix"]
        elk = _find_elk_by_prefix(hass, prefix)
        if elk is None:
            raise HomeAssistantError(f"No ElkM1 with prefix '{prefix}' found")
        return elk

    def _speak_word_service(service: ServiceCall) -> None:
        _getelk(service).panel.speak_word(service.data["number"])

    def _speak_phrase_service(service: ServiceCall) -> None:
        _getelk(service).panel.speak_phrase(service.data["number"])

    def _set_time_service(service: ServiceCall) -> None:
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


def create_elk_entities(
    elk_data: ELKM1Data,
    elk_elements: Iterable[Element],
    element_type: str,
    class_: Any,
    entities: list[ElkEntity],
) -> list[ElkEntity] | None:
    """Create the ElkM1 devices of a particular class."""
    auto_configure = elk_data.auto_configure

    if not auto_configure and not elk_data.config[element_type]["enabled"]:
        return None

    elk = elk_data.elk
    _LOGGER.debug("Creating elk entities for %s", elk)

    for element in elk_elements:
        if auto_configure:
            if not element.configured:
                continue
        # Only check the included list if auto configure is not
        elif not elk_data.config[element_type]["included"][element.index]:
            continue

        entities.append(class_(element, elk, elk_data))
    return entities


class ElkEntity(Entity):
    """Base class for all Elk entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, element: Element, elk: Elk, elk_data: ELKM1Data) -> None:
        """Initialize the base of all Elk devices."""
        self._elk = elk
        self._element = element
        self._mac = elk_data.mac
        self._prefix = elk_data.prefix
        self._temperature_unit: str = elk_data.config["temperature_unit"]
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
        self._attr_name = element.name

    @property
    def unique_id(self) -> str:
        """Return unique id of the element."""
        return self._unique_id

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the default attributes of the element."""
        dict_as_str = {}
        for key, val in self._element.as_dict().items():
            dict_as_str[key] = val.value if isinstance(val, Enum) else val
        return {**dict_as_str, **self.initial_attrs()}

    @property
    def available(self) -> bool:
        """Is the entity available to be updated."""
        return self._elk.is_connected()

    def initial_attrs(self) -> dict[str, Any]:
        """Return the underlying element's attributes as a dict."""
        return {"index": self._element.index + 1}

    def _element_changed(self, element: Element, changeset: dict[str, Any]) -> None:
        pass

    @callback
    def _element_callback(self, element: Element, changeset: dict[str, Any]) -> None:
        """Handle callback from an Elk element that has changed."""
        self._element_changed(element, changeset)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callback for ElkM1 changes and update entity state."""
        self._element.add_callback(self._element_callback)
        self._element_callback(self._element, {})

    @property
    def device_info(self) -> DeviceInfo:
        """Device info connecting via the ElkM1 system."""
        return DeviceInfo(
            name=self._element.name,
            identifiers={(DOMAIN, self._unique_id)},
            via_device=(DOMAIN, f"{self._prefix}_system"),
        )


class ElkAttachedEntity(ElkEntity):
    """An elk entity that is attached to the elk system."""

    @property
    def device_info(self) -> DeviceInfo:
        """Device info for the underlying ElkM1 system."""
        device_name = "ElkM1"
        if self._prefix:
            device_name += f" {self._prefix}"
        device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self._prefix}_system")},
            manufacturer="ELK Products, Inc.",
            model="M1",
            name=device_name,
            sw_version=self._elk.panel.elkm1_version,
        )
        if self._mac:
            device_info[ATTR_CONNECTIONS] = {(CONNECTION_NETWORK_MAC, self._mac)}
        return device_info
