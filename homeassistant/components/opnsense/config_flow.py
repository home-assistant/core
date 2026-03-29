"""Config flow for OPNsense integration."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Mapping, MutableMapping
import inspect
import ipaddress
import logging
import re
import socket
from typing import Any
from urllib.parse import ParseResult, quote_plus, urlparse

import aiohttp
from aiopnsense import OPNsenseClient, UnknownFirmware
import awesomeversion
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_DEVICE_TRACKER_CONSIDER_HOME,
    CONF_DEVICE_TRACKER_ENABLED,
    CONF_DEVICE_TRACKER_SCAN_INTERVAL,
    CONF_DEVICE_UNIQUE_ID,
    CONF_DEVICES,
    CONF_FIRMWARE_VERSION,
    CONF_GRANULAR_SYNC_OPTIONS,
    CONF_MANUAL_DEVICES,
    DEFAULT_DEVICE_TRACKER_CONSIDER_HOME,
    DEFAULT_DEVICE_TRACKER_ENABLED,
    DEFAULT_DEVICE_TRACKER_SCAN_INTERVAL,
    DEFAULT_GRANULAR_SYNC_OPTIONS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SYNC_OPTION_VALUE,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    GRANULAR_SYNC_ITEMS,
    OPNSENSE_MIN_FIRMWARE,
    TRACKED_MACS,
)
from .helpers import is_private_ip

_LOGGER: logging.Logger = logging.getLogger(__name__)

CONF_DEVICE_TRACKING_MODE = "device_tracking_mode"
DEVICE_TRACKING_MODE_DISABLED = "disabled"
DEVICE_TRACKING_MODE_ALL = "all_detected"
DEVICE_TRACKING_MODE_SELECTED = "selected_only"
IMPORT_OPTIONS_KEY = "_import_options"


def is_valid_mac_address(mac: str) -> bool:
    """Check if string is a valid MAC address."""
    return normalize_mac_address(mac) is not None


def normalize_mac_address(mac: object) -> str | None:
    """Normalize MAC addresses to lowercase colon-separated format.

    Parameters
    ----------
    mac : str
        Raw MAC address input.

    Returns:
    -------
    str | None
        Normalized MAC (`aa:bb:cc:dd:ee:ff`) when valid, otherwise ``None``.

    """
    if not isinstance(mac, str):
        return None
    normalized = mac.strip().lower().replace("-", ":")
    mac_regex = re.compile(r"^([0-9a-f]{2}:){5}([0-9a-f]{2})$")
    if not mac_regex.match(normalized):
        return None
    return normalized


def _get_device_tracking_mode(
    device_tracker_enabled: bool, selected_devices: list[str] | None
) -> str:
    """Return the UI tracking mode for the current options.

    Parameters
    ----------
    device_tracker_enabled : bool
        Whether device tracker is enabled in options.
    selected_devices : list[str] | None
        Persisted tracked MAC addresses from the config entry options.

    Returns:
    -------
    str
        The UI mode matching the stored options.

    """
    if not device_tracker_enabled:
        return DEVICE_TRACKING_MODE_DISABLED
    return (
        DEVICE_TRACKING_MODE_SELECTED if selected_devices else DEVICE_TRACKING_MODE_ALL
    )


def _parse_manual_devices(manual_devices: str | None) -> list[str]:
    """Parse manually entered MAC addresses from the options form.

    Parameters
    ----------
    manual_devices : str | None
        Comma- or newline-separated MAC address input.

    Returns:
    -------
    list[str]
        Valid normalized MAC addresses in input order.

    """
    if not isinstance(manual_devices, str):
        return []

    macs: list[str] = []
    for item in re.split(r"[\n,]+", manual_devices):
        if not isinstance(item, str):
            continue
        normalized = normalize_mac_address(item)
        if normalized:
            macs.append(normalized)
    return macs


def _merge_selected_devices(*device_groups: Iterable[str]) -> list[str]:
    """Merge MAC addresses while preserving order and removing duplicates.

    Parameters
    ----------
    *device_groups : Iterable[str]
        MAC address iterables to merge.

    Returns:
    -------
    list[str]
        Unique MAC addresses in first-seen order.

    """
    ordered_devices: OrderedDict[str, None] = OrderedDict()
    for group in device_groups:
        for item in group:
            normalized = normalize_mac_address(item) if isinstance(item, str) else None
            if normalized:
                ordered_devices.setdefault(normalized, None)
    return list(ordered_devices)


def _apply_device_tracking_mode(
    options: MutableMapping[str, Any], tracking_mode: str
) -> None:
    """Apply UI tracking mode to persisted options.

    Parameters
    ----------
    options : MutableMapping[str, Any]
        Options mapping to update.
    tracking_mode : str
        Selected UI tracking mode.

    Returns:
    -------
    None
        This function mutates ``options`` in place.

    """
    options[CONF_DEVICE_TRACKER_ENABLED] = (
        tracking_mode != DEVICE_TRACKING_MODE_DISABLED
    )
    if tracking_mode == DEVICE_TRACKING_MODE_ALL:
        options[CONF_DEVICES] = []


def _apply_sync_defaults(data: MutableMapping[str, Any], *, enabled: bool) -> None:
    """Populate sync keys for the currently exposed granular sync items."""
    for item in GRANULAR_SYNC_ITEMS:
        if enabled:
            data[item] = bool(data.get(item, True))
        else:
            data[item] = bool(data.get(item, DEFAULT_SYNC_OPTION_VALUE))


def _build_selected_device_entries(selected_devices: list[str]) -> dict[str, Any]:
    """Build selector entries from currently configured devices.

    Parameters
    ----------
    selected_devices : list[str]
        Persisted tracked MAC addresses from the options entry.

    Returns:
    -------
    dict[str, Any]
        Mapping of normalized MAC addresses to fallback labels.

    """
    entries: dict[str, Any] = {}
    for device in selected_devices:
        normalized = normalize_mac_address(str(device))
        if not normalized:
            continue
        entries[normalized] = _format_selected_device_label(normalized)
    return entries


def _format_selected_device_label(mac: str) -> str:
    """Format a fallback label for configured MACs not currently detected.

    Parameters
    ----------
    mac : str
        MAC address to display.

    Returns:
    -------
    str
        Human-readable fallback label.

    """
    return f"Not currently detected [{mac}]"


def _format_detected_device_label(entry: Mapping[str, Any]) -> str:
    """Format a device label from an ARP table entry.

    Parameters
    ----------
    entry : Mapping[str, Any]
        ARP entry returned by the OPNsense client.

    Returns:
    -------
    str
        Human-readable device label for the options form.

    """
    normalized_mac = normalize_mac_address(str(entry.get("mac", "")))
    mac = normalized_mac or str(entry.get("mac", "")).lower().strip()
    ip: str = str(entry.get("ip", "")).strip()
    hostname: str = str(entry.get("hostname", "")).strip("?").strip()
    manufacturer: str = str(entry.get("manufacturer", "")).strip()

    label_parts: list[str] = []
    if hostname:
        label_parts.append(hostname)
    elif ip:
        label_parts.append(ip)
    else:
        label_parts.append(mac)

    details: list[str] = []
    if ip and ip != label_parts[0]:
        details.append(ip)
    if manufacturer:
        details.append(manufacturer)

    details.append(mac)
    return f"{label_parts[0]} [{' | '.join(details)}]"


def _device_entry_sort_key(
    mac: str, label: str, ip_by_mac: Mapping[str, str]
) -> tuple[int, tuple[int, int] | str]:
    """Return the sort key for device selector entries.

    Parameters
    ----------
    mac : str
        MAC address for the selector option.
    label : str
        User-facing selector label.
    ip_by_mac : Mapping[str, str]
        Detected IP addresses keyed by MAC address.

    Returns:
    -------
    tuple[int, tuple[int, int] | str]
        Key used to sort fallback labels first and detected devices by IP.

    """
    if label.startswith("Not currently detected"):
        return (0, label)

    ip_value = ip_by_mac.get(mac, "")
    if is_ip_address(ip_value):
        ip_addr = ipaddress.ip_address(ip_value)
        return (1, (ip_addr.version, int(ip_addr)))
    return (2, label)


def is_ip_address(value: str) -> bool:
    """Check if string is a valid IP address."""
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    else:
        return True


def cleanse_sensitive_data(message: str, secrets: list | None = None) -> str:
    """Remove sensitive data from logging messages."""
    secrets = secrets or []
    for secret in secrets:
        if not isinstance(secret, str) or secret == "":
            continue
        message = message.replace(secret, "[redacted]")
        message = message.replace(quote_plus(secret), "[redacted]")
    return message


async def validate_input(
    hass: HomeAssistant,
    user_input: MutableMapping[str, Any],
    config_step: str,
    errors: dict[str, Any],
    expected_id: str | None = None,
) -> dict[str, Any]:
    """Check user input for errors."""
    try:
        await _handle_user_input(
            hass=hass,
            user_input=user_input,
            config_step=config_step,
            expected_id=expected_id,
        )
    except BelowMinFirmware:
        _log_and_set_error(
            errors=errors,
            key="below_min_firmware",
            message=f"OPNsense Firmware of {user_input.get(CONF_FIRMWARE_VERSION)} is below the minimum supported version of {OPNSENSE_MIN_FIRMWARE}",
        )
    except UnknownFirmware:
        _log_and_set_error(
            errors=errors,
            key="unknown_firmware",
            message="Unable to get OPNsense Firmware version",
        )
    except MissingDeviceUniqueID as e:
        _log_and_set_error(
            errors=errors,
            key="missing_device_unique_id",
            message=f"Missing Device Unique ID Error. {type(e).__name__}: {e}",
        )
    except (aiohttp.InvalidURL, InvalidURL) as e:
        _log_and_set_error(
            errors=errors,
            key="invalid_url_format",
            message=f"InvalidURL Error. {type(e).__name__}: {e}",
        )
    except aiohttp.ClientSSLError as e:
        _log_and_set_error(
            errors=errors,
            key="cannot_connect_ssl",
            message=cleanse_sensitive_data(
                f"Aiohttp Error. {type(e).__name__}: {e}",
                [user_input.get(CONF_USERNAME), user_input.get(CONF_PASSWORD)],
            ),
        )
    except (aiohttp.TooManyRedirects, aiohttp.RedirectClientError) as e:
        _log_and_set_error(
            errors=errors,
            key="url_redirect",
            message=cleanse_sensitive_data(
                f"Redirect Error. {type(e).__name__}: {e}",
                [user_input.get(CONF_USERNAME), user_input.get(CONF_PASSWORD)],
            ),
        )
    except (TimeoutError, aiohttp.ServerTimeoutError) as e:
        _log_and_set_error(
            errors=errors,
            key="connect_timeout",
            message=cleanse_sensitive_data(
                f"Timeout Error. {type(e).__name__}: {e}",
                [user_input.get(CONF_USERNAME), user_input.get(CONF_PASSWORD)],
            ),
        )
    except aiohttp.ClientResponseError as e:
        if e.status == 401:
            errors["base"] = "invalid_auth"
        elif e.status == 403:
            errors["base"] = "privilege_missing"
        else:
            errors["base"] = "cannot_connect"
        _LOGGER.error(
            cleanse_sensitive_data(
                f"Aiohttp Error. {type(e).__name__}: {e}",
                [user_input.get(CONF_USERNAME), user_input.get(CONF_PASSWORD)],
            )
        )
    except (aiohttp.ClientError, socket.gaierror) as e:
        _log_and_set_error(
            errors=errors,
            key="cannot_connect",
            message=cleanse_sensitive_data(
                f"Aiohttp Error. {type(e).__name__}: {e}",
                [user_input.get(CONF_USERNAME), user_input.get(CONF_PASSWORD)],
            ),
        )
    except OSError as e:
        error_message = str(e)
        if "unsupported XML-RPC protocol" in error_message:
            errors["base"] = "privilege_missing"
        elif "timed out" in error_message:
            errors["base"] = "connect_timeout"
        elif "SSL:" in error_message:
            errors["base"] = "cannot_connect_ssl"
        else:
            errors["base"] = "unknown"
        _LOGGER.error(
            cleanse_sensitive_data(
                f"Error. {type(e).__name__}: {e}",
                [user_input.get(CONF_USERNAME), user_input.get(CONF_PASSWORD)],
            )
        )
    return errors


async def _clean_and_parse_url(user_input: MutableMapping[str, Any]) -> None:
    """Clean and parse the URL."""
    fix_url: str = user_input.get(CONF_URL, "").strip()
    url_parts: ParseResult = urlparse(fix_url)

    if not url_parts.scheme and not url_parts.netloc:
        fix_url = "https://" + fix_url
        url_parts = urlparse(fix_url)

    if not url_parts.netloc:
        raise InvalidURL

    user_input[CONF_URL] = f"{url_parts.scheme}://{url_parts.netloc}"
    _LOGGER.debug("[config_flow] Cleaned URL: %s", user_input[CONF_URL])


async def _get_client(
    user_input: MutableMapping[str, Any], hass: HomeAssistant
) -> OPNsenseClient:
    """Create and return the OPNsense client."""
    return OPNsenseClient(
        url=user_input[CONF_URL],
        username=user_input[CONF_USERNAME],
        password=user_input[CONF_PASSWORD],
        session=async_create_clientsession(
            hass=hass,
            raise_for_status=True,
            cookie_jar=aiohttp.CookieJar(unsafe=is_private_ip(user_input[CONF_URL])),
        ),
        opts={"verify_ssl": user_input.get(CONF_VERIFY_SSL)},
        initial=True,
    )


def _validate_firmware_version(firmware_version: str) -> None:
    """Validate the firmware version."""
    if awesomeversion.AwesomeVersion(firmware_version) < awesomeversion.AwesomeVersion(
        OPNSENSE_MIN_FIRMWARE
    ):
        raise BelowMinFirmware


async def _close_temp_client(client: OPNsenseClient) -> None:
    """Close a temporary OPNsense client used during config flow validation."""
    for method_name in ("close", "disconnect", "async_close", "aclose"):
        close_method = getattr(client, method_name, None)
        if not callable(close_method):
            continue
        try:
            result = close_method()
            if inspect.isawaitable(result):
                await result
        except (
            aiohttp.ClientError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as err:
            _LOGGER.debug(
                "Unable to close temporary OPNsense client via %s: %s",
                method_name,
                err,
            )
        break


async def _handle_user_input(
    hass: HomeAssistant,
    user_input: MutableMapping[str, Any],
    config_step: str,
    expected_id: str | None = None,
) -> None:
    """Handle and validate the user input."""
    await _clean_and_parse_url(user_input)

    client: OPNsenseClient = await _get_client(user_input, hass)
    try:
        user_input[CONF_FIRMWARE_VERSION] = await client.get_host_firmware_version()
        _LOGGER.debug(
            "[handle_user_input] Firmware Version: %s",
            user_input[CONF_FIRMWARE_VERSION],
        )

        try:
            _validate_firmware_version(user_input[CONF_FIRMWARE_VERSION])
        except (
            awesomeversion.exceptions.AwesomeVersionCompareException,
            TypeError,
            ValueError,
        ) as e:
            raise UnknownFirmware from e

        system_info: dict[str, Any] = await client.get_system_info()
        _LOGGER.debug("[handle_user_input] system_info: %s", system_info)

        if not user_input.get(CONF_NAME):
            user_input[CONF_NAME] = system_info.get("name") or "OPNsense"

        user_input[CONF_DEVICE_UNIQUE_ID] = await client.get_device_unique_id(
            expected_id=expected_id
        )
        _LOGGER.debug(
            "[handle_user_input] Device Unique ID: %s",
            user_input[CONF_DEVICE_UNIQUE_ID],
        )

        if not user_input.get(CONF_DEVICE_UNIQUE_ID):
            raise MissingDeviceUniqueID
    finally:
        await _close_temp_client(client)


def _log_and_set_error(
    errors: MutableMapping[str, Any], key: str, message: str
) -> None:
    """Log the error and set it in the errors dictionary."""
    _LOGGER.error(message)
    errors["base"] = key


def _build_user_input_schema(
    user_input: MutableMapping[str, Any] | None,
    fallback: MutableMapping[str, Any] | None = None,
    reconf: bool = False,
) -> vol.Schema:
    if user_input is None:
        user_input = {}
    if fallback is None:
        fallback = {}

    schema = vol.Schema(
        {
            vol.Required(
                CONF_URL,
                default=user_input.get(CONF_URL, fallback.get(CONF_URL, "https://")),
            ): str,
            vol.Optional(
                CONF_VERIFY_SSL,
                default=user_input.get(
                    CONF_VERIFY_SSL, fallback.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
                ),
            ): bool,
            vol.Required(
                CONF_USERNAME,
                default=user_input.get(CONF_USERNAME, fallback.get(CONF_USERNAME, "")),
            ): str,
            vol.Required(
                CONF_PASSWORD,
                default=user_input.get(CONF_PASSWORD, fallback.get(CONF_PASSWORD, "")),
            ): str,
        }
    )
    if not reconf:
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_NAME,
                    default=user_input.get(CONF_NAME, fallback.get(CONF_NAME, "")),
                ): str,
                vol.Required(
                    CONF_GRANULAR_SYNC_OPTIONS,
                    default=user_input.get(
                        CONF_GRANULAR_SYNC_OPTIONS,
                        fallback.get(
                            CONF_GRANULAR_SYNC_OPTIONS, DEFAULT_GRANULAR_SYNC_OPTIONS
                        ),
                    ),
                ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
            }
        )
    return schema


def _build_granular_sync_schema(
    user_input: MutableMapping[str, Any] | None,
    fallback: MutableMapping[str, Any] | None = None,
) -> vol.Schema:
    if user_input is None:
        user_input = {}
    if fallback is None:
        fallback = {}

    schema_dict: dict[Any, Any] = {}

    for conf in GRANULAR_SYNC_ITEMS:
        schema_dict[
            vol.Optional(
                conf,
                default=user_input.get(
                    conf,
                    fallback.get(conf, DEFAULT_SYNC_OPTION_VALUE),
                ),
            )
        ] = selector.BooleanSelector(selector.BooleanSelectorConfig())

    return vol.Schema(schema_dict)


def _build_options_init_schema(
    user_input: MutableMapping[str, Any] | None,
    fallback_config: MutableMapping[str, Any] | None = None,
    fallback_options: MutableMapping[str, Any] | None = None,
) -> vol.Schema:
    if user_input is None:
        user_input = {}
    if fallback_config is None:
        fallback_config = {}
    if fallback_options is None:
        fallback_options = {}

    tracking_mode = str(
        user_input.get(
            CONF_DEVICE_TRACKING_MODE,
            _get_device_tracking_mode(
                bool(
                    fallback_options.get(
                        CONF_DEVICE_TRACKER_ENABLED, DEFAULT_DEVICE_TRACKER_ENABLED
                    )
                ),
                fallback_options.get(CONF_DEVICES, []),
            ),
        )
    )

    return vol.Schema(
        {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=user_input.get(
                    CONF_SCAN_INTERVAL,
                    fallback_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ),
            ): vol.All(vol.Coerce(int), vol.Clamp(min=10, max=300)),
            vol.Required(
                CONF_DEVICE_TRACKING_MODE,
                default=tracking_mode,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        DEVICE_TRACKING_MODE_DISABLED,
                        DEVICE_TRACKING_MODE_ALL,
                        DEVICE_TRACKING_MODE_SELECTED,
                    ],
                    translation_key=CONF_DEVICE_TRACKING_MODE,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Optional(
                CONF_DEVICE_TRACKER_SCAN_INTERVAL,
                default=user_input.get(
                    CONF_DEVICE_TRACKER_SCAN_INTERVAL,
                    fallback_options.get(
                        CONF_DEVICE_TRACKER_SCAN_INTERVAL,
                        DEFAULT_DEVICE_TRACKER_SCAN_INTERVAL,
                    ),
                ),
            ): vol.All(vol.Coerce(int), vol.Clamp(min=30, max=300)),
            vol.Optional(
                CONF_DEVICE_TRACKER_CONSIDER_HOME,
                default=user_input.get(
                    CONF_DEVICE_TRACKER_CONSIDER_HOME,
                    fallback_options.get(
                        CONF_DEVICE_TRACKER_CONSIDER_HOME,
                        DEFAULT_DEVICE_TRACKER_CONSIDER_HOME,
                    ),
                ),
            ): vol.All(vol.Coerce(int), vol.Clamp(min=0, max=3600)),
            vol.Optional(
                CONF_GRANULAR_SYNC_OPTIONS,
                default=user_input.get(
                    CONF_GRANULAR_SYNC_OPTIONS,
                    fallback_config.get(
                        CONF_GRANULAR_SYNC_OPTIONS, DEFAULT_GRANULAR_SYNC_OPTIONS
                    ),
                ),
            ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
        }
    )


def _build_device_tracker_schema(
    selected_devices: list[str], dt_entries: Mapping[str, Any]
) -> vol.Schema:
    """Build the device tracker options schema.

    Parameters
    ----------
    selected_devices : list[str]
        Previously configured MAC addresses.
    dt_entries : Mapping[str, Any]
        Device choices built from the current ARP table and stored MACs.

    Returns:
    -------
    vol.Schema
        Device tracker form schema.

    """
    return vol.Schema(
        {
            vol.Optional(CONF_DEVICES, default=selected_devices): cv.multi_select(
                dict(dt_entries)
            ),
            vol.Optional(CONF_MANUAL_DEVICES): selector.TextSelector(
                selector.TextSelectorConfig()
            ),
        }
    )


async def _get_dt_entries(
    hass: HomeAssistant, config: Mapping[str, Any], selected_devices: list
) -> dict[str, Any]:
    """Return device-tracker selector entries.

    Parameters
    ----------
    hass : HomeAssistant
        Home Assistant instance.
    config : Mapping[str, Any]
        Config entry data used to build the OPNsense client.
    selected_devices : list
        Persisted MAC addresses that should remain selectable even when not
        currently present in the ARP table.

    Returns:
    -------
    dict[str, Any]
        Mapping of MAC addresses to user-facing labels.

    """
    url = config[CONF_URL].strip()
    username: str = config[CONF_USERNAME]
    password: str = config[CONF_PASSWORD]
    verify_ssl: bool = config.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
    client = OPNsenseClient(
        url=url,
        username=username,
        password=password,
        session=async_create_clientsession(
            hass=hass,
            raise_for_status=False,
            cookie_jar=aiohttp.CookieJar(unsafe=is_private_ip(url)),
        ),
        opts={"verify_ssl": verify_ssl},
    )
    # dicts are ordered so put all previously selected items at the top
    entries: dict[str, Any] = _build_selected_device_entries(selected_devices)
    try:
        arp_table: list = await client.get_arp_table(resolve_hostnames=True)
        if arp_table:
            ip_by_mac: dict[str, str] = {}
            # follow with all arp table entries
            for entry in arp_table:
                normalized_mac = normalize_mac_address(str(entry.get("mac", "")))
                mac: str = normalized_mac or str(entry.get("mac", "")).lower().strip()
                if len(mac) < 1:
                    continue
                ip_by_mac[mac] = str(entry.get("ip", "")).strip()
                label: str = _format_detected_device_label(entry)
                entries[mac] = label

            # Sort entries: fallback labels first, then by IP address (ascending)
            sorted_entries: dict[str, Any] = dict(
                sorted(
                    entries.items(),
                    key=lambda item: _device_entry_sort_key(
                        item[0], item[1], ip_by_mac
                    ),
                )
            )
            return sorted_entries
    finally:
        await _close_temp_client(client)
    return entries


class OPNsenseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OPNsense."""

    # bumping this is what triggers async_migrate_entry for the component
    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._config: dict[str, Any] = {}

    # gets invoked without user input initially
    # when user submits has user_input
    async def async_step_user(
        self, user_input: MutableMapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, Any] = {}
        if user_input is not None:
            errors = await validate_input(
                hass=self.hass, user_input=user_input, config_step="user", errors=errors
            )
            if not errors:
                # https://developers.home-assistant.io/docs/config_entries_config_flow_handler#unique-ids
                await self.async_set_unique_id(user_input.get(CONF_DEVICE_UNIQUE_ID))
                self._abort_if_unique_id_configured()

                if user_input[CONF_GRANULAR_SYNC_OPTIONS]:
                    self._config = dict(user_input)
                    _apply_sync_defaults(self._config, enabled=False)
                    return await self.async_step_granular_sync()

                config = dict(user_input)
                _apply_sync_defaults(config, enabled=True)
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=config,
                )

        if not user_input:
            user_input = {}
        firmware = user_input.get(CONF_FIRMWARE_VERSION, "Unknown")

        return self.async_show_form(
            step_id="user",
            data_schema=_build_user_input_schema(user_input=user_input),
            errors=errors,
            description_placeholders={
                "firmware": firmware,
                "min_firmware": OPNSENSE_MIN_FIRMWARE,
            },
        )

    async def async_step_granular_sync(
        self, user_input: MutableMapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step for initial granular sync options."""
        errors: dict[str, Any] = {}
        if user_input is not None:
            self._config.update(user_input)
            _apply_sync_defaults(self._config, enabled=False)
            errors = await validate_input(
                hass=self.hass,
                user_input=self._config,
                config_step="granular_sync",
                errors=errors,
                expected_id=self._config.get(CONF_DEVICE_UNIQUE_ID),
            )
            if not errors:
                return self.async_create_entry(
                    title=self._config[CONF_NAME],
                    data=self._config,
                )

        if not user_input:
            user_input = {}

        return self.async_show_form(
            step_id="granular_sync",
            data_schema=_build_granular_sync_schema(user_input=user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: MutableMapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Config flow reconfigure step."""
        errors: dict[str, Any] = {}
        reconfigure_entry = self._get_reconfigure_entry()
        self._config = dict(reconfigure_entry.data)

        if user_input is not None:
            self._config.update(user_input)
            errors = await validate_input(
                hass=self.hass,
                user_input=self._config,
                config_step="reconfigure",
                errors=errors,
                expected_id=self._config.get(CONF_DEVICE_UNIQUE_ID),
            )

            if not errors:
                await self.async_set_unique_id(self._config.get(CONF_DEVICE_UNIQUE_ID))
                self._abort_if_unique_id_mismatch()

                return self.async_update_reload_and_abort(
                    entry=reconfigure_entry,
                    data=self._config,
                )

        if not user_input:
            user_input = {}
        firmware = user_input.get(CONF_FIRMWARE_VERSION, "Unknown")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_user_input_schema(
                user_input=user_input, fallback=self._config, reconf=True
            ),
            errors=errors,
            description_placeholders={
                "firmware": firmware,
                "min_firmware": OPNSENSE_MIN_FIRMWARE,
            },
        )

    async def async_step_import(
        self, user_input: MutableMapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle import."""
        options = dict(user_input.pop(IMPORT_OPTIONS_KEY, {}))
        _apply_sync_defaults(
            user_input,
            enabled=not user_input.get(CONF_GRANULAR_SYNC_OPTIONS, False),
        )
        errors = await validate_input(
            hass=self.hass,
            user_input=user_input,
            config_step="import",
            errors={},
        )
        if errors:
            return self.async_abort(reason=next(iter(errors.values()), "unknown"))

        await self.async_set_unique_id(user_input.get(CONF_DEVICE_UNIQUE_ID))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data=dict(user_input),
            options=options,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: MutableMapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reauth confirmation step."""
        errors: dict[str, Any] = {}
        reauth_entry = self._get_reauth_entry()
        self._config = dict(reauth_entry.data)

        if user_input is not None:
            self._config.update(user_input)
            errors = await validate_input(
                hass=self.hass,
                user_input=self._config,
                config_step="reconfigure",
                errors=errors,
                expected_id=self._config.get(CONF_DEVICE_UNIQUE_ID),
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    entry=reauth_entry,
                    data_updates=self._config,
                )

        if not user_input:
            user_input = {}
        firmware = user_input.get(CONF_FIRMWARE_VERSION, "Unknown")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_build_user_input_schema(
                user_input=user_input, fallback=self._config, reconf=True
            ),
            errors=errors,
            description_placeholders={
                "firmware": firmware,
                "min_firmware": OPNSENSE_MIN_FIRMWARE,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OPNsenseOptionsFlow:
        """Get the options flow for this handler."""
        return OPNsenseOptionsFlow(config_entry)


class OPNsenseOptionsFlow(OptionsFlow):
    """Handle option flow for OPNsense."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        # Store the config entry passed by the ConfigFlow helper so tests and
        # runtime code can access it. Some test harnesses assign directly to
        # `config_entry` on the flow; provide a backing attribute and a
        # property with a setter to maintain compatibility.
        self._config_entry: ConfigEntry = config_entry
        self._config: dict[str, Any] = {}
        self._options: dict[str, Any] = {}

    @property
    def config_entry(self) -> ConfigEntry:
        """Return the config entry associated with this options flow."""
        return self._config_entry

    @config_entry.setter
    def config_entry(self, entry: ConfigEntry) -> None:
        """Allow assigning the config entry."""
        self._config_entry = entry

    async def async_step_init(
        self, user_input: MutableMapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        errors: dict[str, Any] = {}
        self._config = dict(self.config_entry.data)
        self._options = dict(self.config_entry.options)
        if user_input is not None:
            tracking_mode = str(
                user_input.get(
                    CONF_DEVICE_TRACKING_MODE,
                    _get_device_tracking_mode(
                        bool(self._options.get(CONF_DEVICE_TRACKER_ENABLED, False)),
                        self._options.get(CONF_DEVICES, []),
                    ),
                )
            )
            self._options.update(
                {
                    key: value
                    for key, value in user_input.items()
                    if key != CONF_DEVICE_TRACKING_MODE
                }
            )
            _apply_device_tracking_mode(self._options, tracking_mode)
            # Keep the chosen mode in-flow so multi-step options paths can branch
            # consistently before final save.
            self._options[CONF_DEVICE_TRACKING_MODE] = tracking_mode
            self._config[CONF_GRANULAR_SYNC_OPTIONS] = self._options.pop(
                CONF_GRANULAR_SYNC_OPTIONS, DEFAULT_GRANULAR_SYNC_OPTIONS
            )
            if self._config.get(CONF_GRANULAR_SYNC_OPTIONS):
                _apply_sync_defaults(self._config, enabled=False)
                return await self.async_step_granular_sync()
            _apply_sync_defaults(self._config, enabled=True)
            if tracking_mode == DEVICE_TRACKING_MODE_SELECTED:
                return await self.async_step_device_tracker()

            if not errors:
                self._options.pop(CONF_DEVICE_TRACKING_MODE, None)
                self.hass.config_entries.async_update_entry(
                    entry=self.config_entry, data=self._config, options=self._options
                )
                return self.async_create_entry(data=self._options)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_options_init_schema(
                user_input=user_input,
                fallback_config=self._config,
                fallback_options=self._options,
            ),
            errors=errors,
        )

    async def async_step_granular_sync(
        self, user_input: MutableMapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step for granular sync options."""
        errors: dict[str, Any] = {}
        if user_input is not None:
            self._config.update(user_input)
            _apply_sync_defaults(self._config, enabled=False)
            errors = await validate_input(
                hass=self.hass,
                user_input=self._config,
                config_step="granular_sync",
                errors=errors,
                expected_id=self._config.get(CONF_DEVICE_UNIQUE_ID),
            )
            if not errors:
                tracking_mode = str(
                    self._options.get(
                        CONF_DEVICE_TRACKING_MODE,
                        _get_device_tracking_mode(
                            bool(self._options.get(CONF_DEVICE_TRACKER_ENABLED, False)),
                            self._options.get(CONF_DEVICES, []),
                        ),
                    )
                )
                if tracking_mode == DEVICE_TRACKING_MODE_SELECTED:
                    return await self.async_step_device_tracker()
                _LOGGER.debug(
                    "Updating options from granular sync. user_input: %s", self._config
                )

                self._options.pop(CONF_DEVICE_TRACKING_MODE, None)
                self.hass.config_entries.async_update_entry(
                    entry=self.config_entry, data=self._config, options=self._options
                )
                return self.async_create_entry(data=self._options)

        if not user_input:
            user_input = {}

        return self.async_show_form(
            step_id="granular_sync",
            data_schema=_build_granular_sync_schema(
                user_input=user_input,
                fallback=self._config,
            ),
            errors=errors,
        )

    async def async_step_device_tracker(
        self, user_input: MutableMapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the device tracker options step.

        Parameters
        ----------
        user_input : MutableMapping[str, Any] | None
            User-submitted form data.

        Returns:
        -------
        ConfigFlowResult
            The next form step or the saved options entry.

        """
        errors: dict[str, Any] = {}
        selected_devices: list[str] = _merge_selected_devices(
            self._options.get(CONF_DEVICES, [])
        )
        if user_input is not None:
            self._options.update(
                {
                    key: value
                    for key, value in user_input.items()
                    if key not in (CONF_DEVICE_TRACKING_MODE, CONF_MANUAL_DEVICES)
                }
            )
            manual_devices = _parse_manual_devices(user_input.get(CONF_MANUAL_DEVICES))
            selected_from_form = user_input.get(CONF_DEVICES, [])
            self._options[CONF_DEVICES] = _merge_selected_devices(
                selected_from_form, manual_devices
            )
            if not self._options.get(CONF_DEVICE_TRACKER_ENABLED):
                self._options.pop(CONF_DEVICES, None)
                self._config.pop(TRACKED_MACS, None)

            if not errors:
                self._options.pop(CONF_DEVICE_TRACKING_MODE, None)
                self.hass.config_entries.async_update_entry(
                    entry=self.config_entry, data=self._config, options=self._options
                )
                return self.async_create_entry(data=self._options)

        try:
            dt_entries: dict[str, Any] = await _get_dt_entries(
                hass=self.hass,
                config=self.config_entry.data,
                selected_devices=selected_devices,
            )
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            _LOGGER.warning("Failed to load device tracker entries: %s", err)
            errors["base"] = "cannot_connect"
            dt_entries = {
                mac: _format_selected_device_label(mac)
                for mac in _merge_selected_devices(selected_devices)
            }

        return self.async_show_form(
            step_id="device_tracker",
            data_schema=_build_device_tracker_schema(
                selected_devices=selected_devices,
                dt_entries=dt_entries,
            ),
            errors=errors,
        )


class InvalidURL(Exception):
    """InvalidURL."""


class MissingDeviceUniqueID(Exception):
    """Missing the Device Unique ID."""


class BelowMinFirmware(Exception):
    """Current firmware is below the Minimum supported version."""
