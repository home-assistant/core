"""Support the ElkM1 Gold and ElkM1 EZ8 alarm/integration panels."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from elkm1_lib.elements import Element
from elkm1_lib.elk import Elk
from elkm1_lib.util import parse_url
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
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
from .services import async_setup_services

type ElkM1ConfigEntry = ConfigEntry[ELKM1Data]

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


def hostname_from_url(url: str) -> str:
    """Return the hostname from a url."""
    return parse_url(url)[1]


def _host_validator(config: dict[str, str]) -> dict[str, str]:
    """Validate that a host is properly configured."""
    if config[CONF_HOST].startswith(("elks://", "elksv1_2://")):
        if CONF_USERNAME not in config or CONF_PASSWORD not in config:
            raise vol.Invalid(
                "Specify username and password for elks:// or elksv1_2://"
            )
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
    ),
    _host_validator,
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [DEVICE_SCHEMA], _has_all_unique_prefixes)},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, hass_config: ConfigType) -> bool:
    """Set up the Elk M1 platform."""
    async_setup_services(hass)

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


async def async_setup_entry(hass: HomeAssistant, entry: ElkM1ConfigEntry) -> bool:
    """Set up Elk-M1 Control from a config entry."""
    conf = entry.data

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

    sync_success = False
    try:
        await ElkSyncWaiter(elk, LOGIN_TIMEOUT, SYNC_TIMEOUT).async_wait()
        sync_success = True
    except LoginFailed:
        _LOGGER.error("ElkM1 login failed for %s", conf[CONF_HOST])
        return False
    except TimeoutError as exc:
        raise ConfigEntryNotReady(f"Timed out connecting to {conf[CONF_HOST]}") from exc
    finally:
        if not sync_success:
            elk.disconnect()

    elk_temp_unit = elk.panel.temperature_units
    if elk_temp_unit == "C":
        temperature_unit = UnitOfTemperature.CELSIUS
    else:
        temperature_unit = UnitOfTemperature.FAHRENHEIT
    config["temperature_unit"] = temperature_unit
    prefix: str = conf[CONF_PREFIX]
    auto_configure: bool = conf[CONF_AUTO_CONFIGURE]
    entry.runtime_data = ELKM1Data(
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


async def async_unload_entry(hass: HomeAssistant, entry: ElkM1ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # disconnect cleanly
    entry.runtime_data.elk.disconnect()
    return unload_ok


class LoginFailed(Exception):
    """Raised when login to ElkM1 fails."""


class ElkSyncWaiter:
    """Wait for ElkM1 to sync."""

    def __init__(self, elk: Elk, login_timeout: int, sync_timeout: int) -> None:
        """Initialize the sync waiter."""
        self._elk = elk
        self._login_timeout = login_timeout
        self._sync_timeout = sync_timeout
        self._loop = asyncio.get_running_loop()
        self._sync_future: asyncio.Future[None] = self._loop.create_future()
        self._login_future: asyncio.Future[None] = self._loop.create_future()

    @callback
    def _async_set_future_if_not_done(self, future: asyncio.Future[None]) -> None:
        """Set the future result if not already done."""
        if not future.done():
            future.set_result(None)

    @callback
    def _async_login_status(self, succeeded: bool) -> None:
        """Handle login status callback."""
        if succeeded:
            _LOGGER.debug("ElkM1 login succeeded")
            self._async_set_future_if_not_done(self._login_future)
        else:
            _LOGGER.error("ElkM1 login failed; invalid username or password")
            self._async_set_exception_if_not_done(self._login_future, LoginFailed)

    @callback
    def _async_set_exception_if_not_done(
        self, future: asyncio.Future[None], exception: type[Exception]
    ) -> None:
        """Set an exception on the future if not already done."""
        if not future.done():
            future.set_exception(exception())

    @callback
    def _async_sync_complete(self) -> None:
        """Handle sync complete callback."""
        self._async_set_future_if_not_done(self._sync_future)

    async def async_wait(self) -> None:
        """Wait for login and sync to complete.

        Raises LoginFailed if login fails.
        Raises TimeoutError if login or sync times out.
        """
        self._elk.add_handler("login", self._async_login_status)
        self._elk.add_handler("sync_complete", self._async_sync_complete)

        try:
            for name, future, timeout in (
                ("login", self._login_future, self._login_timeout),
                ("sync_complete", self._sync_future, self._sync_timeout),
            ):
                _LOGGER.debug("Waiting for %s event for %s seconds", name, timeout)
                handle = self._loop.call_later(
                    timeout, self._async_set_exception_if_not_done, future, TimeoutError
                )
                try:
                    await future
                finally:
                    handle.cancel()

                _LOGGER.debug("Received %s event", name)
        finally:
            self._elk.remove_handler("login", self._async_login_status)
            self._elk.remove_handler("sync_complete", self._async_sync_complete)
