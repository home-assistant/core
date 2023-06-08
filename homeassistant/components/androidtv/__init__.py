"""Support for functionality to interact with Android/Fire TV devices."""
from __future__ import annotations

from collections.abc import Mapping
import os
from typing import Any

from adb_shell.auth.keygen import keygen
from adb_shell.exceptions import (
    AdbTimeoutError,
    InvalidChecksumError,
    InvalidCommandError,
    InvalidResponseError,
    TcpTimeoutException,
)
from androidtv.adb_manager.adb_manager_sync import ADBPythonSync, PythonRSASigner
from androidtv.setup_async import (
    AndroidTVAsync,
    FireTVAsync,
    setup as async_androidtv_setup,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    ANDROID_DEV,
    ANDROID_DEV_OPT,
    CONF_ADB_SERVER_IP,
    CONF_ADB_SERVER_PORT,
    CONF_ADBKEY,
    CONF_STATE_DETECTION_RULES,
    DEFAULT_ADB_SERVER_PORT,
    DEVICE_ANDROIDTV,
    DEVICE_FIRETV,
    DOMAIN,
    PROP_ETHMAC,
    PROP_WIFIMAC,
    SIGNAL_CONFIG_ENTITY,
)

ADB_PYTHON_EXCEPTIONS: tuple = (
    AdbTimeoutError,
    BrokenPipeError,
    ConnectionResetError,
    ValueError,
    InvalidChecksumError,
    InvalidCommandError,
    InvalidResponseError,
    TcpTimeoutException,
)
ADB_TCP_EXCEPTIONS: tuple = (ConnectionResetError, RuntimeError)

PLATFORMS = [Platform.MEDIA_PLAYER]
RELOAD_OPTIONS = [CONF_STATE_DETECTION_RULES]

_INVALID_MACS = {"ff:ff:ff:ff:ff:ff"}


def get_androidtv_mac(dev_props: dict[str, Any]) -> str | None:
    """Return formatted mac from device properties."""
    for prop_mac in (PROP_ETHMAC, PROP_WIFIMAC):
        if if_mac := dev_props.get(prop_mac):
            mac = format_mac(if_mac)
            if mac not in _INVALID_MACS:
                return mac
    return None


def _setup_androidtv(
    hass: HomeAssistant, config: Mapping[str, Any]
) -> tuple[str, PythonRSASigner | None, str]:
    """Generate an ADB key (if needed) and load it."""
    adbkey: str = config.get(
        CONF_ADBKEY, hass.config.path(STORAGE_DIR, "androidtv_adbkey")
    )
    if CONF_ADB_SERVER_IP not in config:
        # Use "adb_shell" (Python ADB implementation)
        if not os.path.isfile(adbkey):
            # Generate ADB key files
            keygen(adbkey)

        # Load the ADB key
        signer = ADBPythonSync.load_adbkey(adbkey)
        adb_log = f"using Python ADB implementation with adbkey='{adbkey}'"

    else:
        # Use "pure-python-adb" (communicate with ADB server)
        signer = None
        adb_log = (
            "using ADB server at"
            f" {config[CONF_ADB_SERVER_IP]}:{config[CONF_ADB_SERVER_PORT]}"
        )

    return adbkey, signer, adb_log


async def async_connect_androidtv(
    hass: HomeAssistant,
    config: Mapping[str, Any],
    *,
    state_detection_rules: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> tuple[AndroidTVAsync | FireTVAsync | None, str | None]:
    """Connect to Android device."""
    address = f"{config[CONF_HOST]}:{config[CONF_PORT]}"

    adbkey, signer, adb_log = await hass.async_add_executor_job(
        _setup_androidtv, hass, config
    )

    aftv = await async_androidtv_setup(
        config[CONF_HOST],
        config[CONF_PORT],
        adbkey,
        config.get(CONF_ADB_SERVER_IP),
        config.get(CONF_ADB_SERVER_PORT, DEFAULT_ADB_SERVER_PORT),
        state_detection_rules,
        config[CONF_DEVICE_CLASS],
        timeout,
        signer,
    )

    if not aftv.available:
        # Determine the name that will be used for the device in the log
        if config[CONF_DEVICE_CLASS] == DEVICE_ANDROIDTV:
            device_name = "Android device"
        elif config[CONF_DEVICE_CLASS] == DEVICE_FIRETV:
            device_name = "Fire TV device"
        else:
            device_name = "Android / Fire TV device"

        error_message = f"Could not connect to {device_name} at {address} {adb_log}"
        return None, error_message

    return aftv, None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Android Debug Bridge platform."""

    state_det_rules = entry.options.get(CONF_STATE_DETECTION_RULES)
    if CONF_ADB_SERVER_IP not in entry.data:
        exceptions = ADB_PYTHON_EXCEPTIONS
    else:
        exceptions = ADB_TCP_EXCEPTIONS

    try:
        aftv, error_message = await async_connect_androidtv(
            hass, entry.data, state_detection_rules=state_det_rules
        )
    except exceptions as exc:
        raise ConfigEntryNotReady(exc) from exc

    if not aftv:
        raise ConfigEntryNotReady(error_message)

    async def async_close_connection(event):
        """Close Android Debug Bridge connection on HA Stop."""
        await aftv.adb_close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )
    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        ANDROID_DEV: aftv,
        ANDROID_DEV_OPT: entry.options.copy(),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        aftv = hass.data[DOMAIN][entry.entry_id][ANDROID_DEV]
        await aftv.adb_close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update when config_entry options update."""
    reload_opt = False
    old_options = hass.data[DOMAIN][entry.entry_id][ANDROID_DEV_OPT]
    for opt_key, opt_val in entry.options.items():
        if opt_key in RELOAD_OPTIONS:
            old_val = old_options.get(opt_key)
            if old_val is None or old_val != opt_val:
                reload_opt = True
                break

    if reload_opt:
        await hass.config_entries.async_reload(entry.entry_id)
        return

    hass.data[DOMAIN][entry.entry_id][ANDROID_DEV_OPT] = entry.options.copy()
    async_dispatcher_send(hass, f"{SIGNAL_CONFIG_ENTITY}_{entry.entry_id}")
