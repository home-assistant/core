"""Attribution of serial ports to the integrations and apps using them."""

from collections.abc import Iterator, Mapping, Sequence
import os
import re
from typing import Any

from homeassistant.components.hassio import HassioNotReadyError, get_addons_info
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.hassio import is_hassio
from homeassistant.loader import async_get_integrations

from .const import DOMAIN
from .models import SerialDevice, SerialPortConsumer, USBDevice

# Key paths holding a serial port in the config entry data and options of
# searched integrations. Traversed literally, never recursively.
SERIAL_PORT_KEY_PATHS: tuple[tuple[str, ...], ...] = (
    ("device",),
    ("device", "path"),  # zha
    ("device_path",),  # alarmdecoder
    ("filename",),  # bryant_evolution
    ("host",),  # elkm1
    ("port",),
    ("serial_port",),  # edl21, teleinfo
    ("socket_path",),  # zwave_js
    ("usb_path",),  # zwave_js, crownstone
)

# Integrations configured with a serial port but not depending on `usb`
NON_USB_SERIAL_DOMAINS = ("alarmdecoder", "bryant_evolution", "elkm1", "mysensors")

# States in which the entry claims its configured port, even if the port is not
# open right now: a retrying setup typically failed to open the port, while an
# unloading or failed-to-unload entry may still hold it
ACTIVE_CONFIG_ENTRY_STATES = (
    ConfigEntryState.LOADED,
    ConfigEntryState.SETUP_RETRY,
    ConfigEntryState.SETUP_IN_PROGRESS,
    ConfigEntryState.UNLOAD_IN_PROGRESS,
    ConfigEntryState.FAILED_UNLOAD,
)

# Remote ports contributed by serial port scanners; a configured port missing
# from the scan is absent, e.g. because the providing integration is offline
SCANNED_PORT_SCHEMES = ("esphome-hass://",)

# Serial port URLs no scanner contributes; they can never be scanned, so a
# claiming consumer is the only evidence such a port exists
UNSCANNABLE_PORT_SCHEMES = (
    "esphome://",
    "rfc2217://",
    "socket://",
    "tcp://",
)

# upb wraps the port in a URL with an optional baud rate, e.g.
# `serial:///dev/ttyS0:4800`, which upb_lib strips itself when connecting
BAUD_SUFFIX_RE = re.compile(r":\d+$")

# Supervisor app state, mirrors `aiohasupervisor.models.AddonState.STARTED`
APP_STATE_STARTED = "started"


def _resolve_key_path(data: Mapping[str, Any], key_path: tuple[str, ...]) -> Any:
    """Return the value at a key path, or `None` if the path does not exist."""
    value: Any = data

    for key in key_path:
        if not isinstance(value, Mapping) or key not in value:
            return None
        value = value[key]

    return value


def _serial_port_from_value(
    value: Any, known_devices: set[str], domain: str
) -> str | None:
    """Return the serial port a config entry value refers to."""
    if not isinstance(value, str):
        return None

    if value in known_devices:
        return value

    if value.startswith(SCANNED_PORT_SCHEMES):
        return value

    if value.startswith(UNSCANNABLE_PORT_SCHEMES):
        # zwave_js's esphome:// socket path embeds the noise PSK as `?key=`
        return value.partition("?")[0]

    path = value

    if domain in ("elkm1", "upb"):
        path = path.removeprefix("serial://").removeprefix("device://")
        path = BAUD_SUFFIX_RE.sub("", path)

    if path.startswith("/dev/"):
        return path

    return None


def _resolve_paths(paths: set[str]) -> dict[str, str]:
    """Resolve symlinks of local device paths, passing other values through."""
    return {
        path: os.path.realpath(path) if path.startswith("/") else path for path in paths
    }


async def _async_get_config_entry_consumers(
    hass: HomeAssistant, known_devices: set[str]
) -> dict[str, list[SerialPortConsumer]]:
    """Return serial ports configured in config entries of `usb` integrations."""
    entries = hass.config_entries.async_entries(include_ignore=False)
    integrations = await async_get_integrations(
        hass, {entry.domain for entry in entries}
    )
    consumers: dict[str, list[SerialPortConsumer]] = {}

    for entry in entries:
        integration = integrations[entry.domain]

        if isinstance(integration, Exception):
            continue

        if (
            entry.domain not in NON_USB_SERIAL_DOMAINS
            and DOMAIN not in integration.dependencies
            and DOMAIN not in integration.after_dependencies
        ):
            continue

        for key_path in SERIAL_PORT_KEY_PATHS:
            for data in (entry.data, entry.options):
                port = _serial_port_from_value(
                    _resolve_key_path(data, key_path), known_devices, entry.domain
                )

                if port is None:
                    continue

                consumers.setdefault(port, []).append(
                    SerialPortConsumer(
                        kind="config_entry",
                        title=entry.title,
                        active=entry.state in ACTIVE_CONFIG_ENTRY_STATES,
                        domain=entry.domain,
                        config_entry_id=entry.entry_id,
                    )
                )

    return consumers


def _iter_option_device_paths(value: Any) -> Iterator[str]:
    """Yield device paths configured anywhere in the options of an app."""
    if isinstance(value, str):
        if value.startswith("/dev/"):
            yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _iter_option_device_paths(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_option_device_paths(item)


@callback
def _async_get_app_consumers(
    hass: HomeAssistant,
) -> dict[str, list[SerialPortConsumer]]:
    """Return devices configured in the options of apps.

    The `devices` field of an app also lists the static devices of its manifest,
    which are mapped into the container whether the app uses them or not, so only
    options are evidence of a device being used. Options can refer to devices
    that no longer exist or are not serial ports.
    """
    if not is_hassio(hass):
        return {}

    try:
        apps_info = get_addons_info(hass)
    except HassioNotReadyError:
        return {}

    consumers: dict[str, list[SerialPortConsumer]] = {}

    for slug, info in apps_info.items():
        if info is None:
            continue

        for device in _iter_option_device_paths(info["options"]):
            consumers.setdefault(device, []).append(
                SerialPortConsumer(
                    kind="app",
                    title=info["name"],
                    active=info["state"] == APP_STATE_STARTED,
                    slug=slug,
                )
            )

    return consumers


async def async_get_serial_port_consumers(
    hass: HomeAssistant, ports: Sequence[USBDevice | SerialDevice]
) -> dict[str, list[SerialPortConsumer]]:
    """Return the consumers of every serial port, keyed by device path.

    Scanned ports are keyed by their scanned device path, ports that are configured
    but not currently present are keyed by their configured path.
    """
    known_devices = {port.device for port in ports}

    entry_consumers = await _async_get_config_entry_consumers(hass, known_devices)
    app_consumers = _async_get_app_consumers(hass)

    resolved = await hass.async_add_executor_job(
        _resolve_paths, known_devices | set(entry_consumers) | set(app_consumers)
    )

    # A port can be referred to by any of its symlinks, e.g. `/dev/serial/by-id`
    aliases: dict[str, str] = {}

    for port in ports:
        aliases[resolved[port.device]] = port.device
        aliases[port.device] = port.device

    consumers: dict[str, list[SerialPortConsumer]] = {}

    for path, path_consumers in entry_consumers.items():
        # Ports that are configured but missing are kept and shown as absent
        device = aliases.get(resolved[path], path)
        consumers.setdefault(device, []).extend(path_consumers)

    for path, path_consumers in app_consumers.items():
        # Options can name non-serial devices, only scanned ports are of interest
        resolved_path = resolved[path]

        if resolved_path not in aliases:
            continue

        consumers.setdefault(aliases[resolved_path], []).extend(path_consumers)

    return {
        device: list(dict.fromkeys(device_consumers))
        for device, device_consumers in consumers.items()
    }
