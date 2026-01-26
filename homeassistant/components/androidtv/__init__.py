"""Support for functionality to interact with Android/Fire TV devices."""

from __future__ import annotations

from asyncio import timeout
from collections.abc import Mapping
from dataclasses import dataclass
import logging
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
from androidtvremote2 import (
    AndroidTVRemote,
    CannotConnect,
    ConnectionClosed,
    InvalidAuth,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ADB_SERVER_IP,
    CONF_ADB_SERVER_PORT,
    CONF_ADBKEY,
    CONF_CONNECTION_TYPE,
    CONF_SCREENCAP_INTERVAL,
    CONF_STATE_DETECTION_RULES,
    CONNECTION_TYPE_ADB,
    CONNECTION_TYPE_REMOTE,
    DEFAULT_ADB_SERVER_PORT,
    DEVICE_ANDROIDTV,
    DEVICE_FIRETV,
    DOMAIN,
    PROP_ETHMAC,
    PROP_WIFIMAC,
    SIGNAL_CONFIG_ENTITY,
)
from .helpers import create_remote_api, get_enable_ime
from .services import async_setup_services

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

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.BUTTON, Platform.MEDIA_PLAYER, Platform.REMOTE]
RELOAD_OPTIONS = [CONF_STATE_DETECTION_RULES]

# Domain of the legacy androidtv_remote integration
ANDROIDTV_REMOTE_DOMAIN = "androidtv_remote"

_INVALID_MACS = {"ff:ff:ff:ff:ff:ff"}

_LOGGER = logging.getLogger(__name__)


@dataclass
class AndroidTVADBRuntimeData:
    """Runtime data definition for ADB connection."""

    aftv: AndroidTVAsync | FireTVAsync
    dev_opt: dict[str, Any]


@dataclass
class AndroidTVRemoteRuntimeData:
    """Runtime data definition for Remote protocol connection."""

    api: AndroidTVRemote
    dev_opt: dict[str, Any]


# Union type for runtime data
type AndroidTVRuntimeData = AndroidTVADBRuntimeData | AndroidTVRemoteRuntimeData
AndroidTVConfigEntry = ConfigEntry[AndroidTVRuntimeData]


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
        # Communicate via ADB server
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
    timeout_seconds: float = 30.0,
) -> tuple[AndroidTVAsync | FireTVAsync | None, str | None]:
    """Connect to Android device via ADB."""
    address = f"{config[CONF_HOST]}:{config[CONF_PORT]}"

    adbkey, signer, adb_log = await hass.async_add_executor_job(
        _setup_androidtv, hass, config
    )

    aftv = await async_androidtv_setup(
        host=config[CONF_HOST],
        port=config[CONF_PORT],
        adbkey=adbkey,
        adb_server_ip=config.get(CONF_ADB_SERVER_IP),
        adb_server_port=config.get(CONF_ADB_SERVER_PORT, DEFAULT_ADB_SERVER_PORT),
        state_detection_rules=state_detection_rules,
        device_class=config[CONF_DEVICE_CLASS],
        auth_timeout_s=timeout_seconds,
        signer=signer,
        log_errors=False,
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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s", entry.version, entry.minor_version
    )

    if entry.version == 1:
        new_options = {**entry.options}

        # Migrate MinorVersion 1 -> MinorVersion 2: New option
        if entry.minor_version < 2:
            new_options = {**new_options, CONF_SCREENCAP_INTERVAL: 0}

            hass.config_entries.async_update_entry(
                entry, options=new_options, minor_version=2, version=1
            )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        entry.version,
        entry.minor_version,
    )

    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Android TV integration."""
    async_setup_services(hass)

    # Migrate any existing androidtv_remote entries to androidtv
    await _async_migrate_androidtv_remote_entries(hass)

    return True


async def _async_migrate_androidtv_remote_entries(hass: HomeAssistant) -> None:
    """Migrate androidtv_remote config entries to androidtv integration."""
    # Get all androidtv_remote entries
    old_entries = hass.config_entries.async_entries(ANDROIDTV_REMOTE_DOMAIN)
    if not old_entries:
        return

    _LOGGER.info(
        "Found %d androidtv_remote entries to migrate to androidtv",
        len(old_entries),
    )

    for old_entry in old_entries:
        await _async_migrate_single_entry(hass, old_entry)


async def _async_migrate_single_entry(
    hass: HomeAssistant,
    old_entry: ConfigEntry,
) -> None:
    """Migrate a single androidtv_remote entry to androidtv."""
    _LOGGER.info(
        "Migrating androidtv_remote entry '%s' (%s) to androidtv",
        old_entry.title,
        old_entry.entry_id,
    )

    # Build new entry data with connection_type: remote
    new_data = {
        CONF_HOST: old_entry.data[CONF_HOST],
        CONF_NAME: old_entry.data[CONF_NAME],
        CONF_MAC: old_entry.data[CONF_MAC],
        CONF_CONNECTION_TYPE: CONNECTION_TYPE_REMOTE,
    }

    # Check if an androidtv entry with the same unique_id already exists
    existing_entries = hass.config_entries.async_entries(DOMAIN)
    for existing in existing_entries:
        if existing.unique_id == old_entry.unique_id:
            _LOGGER.warning(
                "Android TV entry with unique_id %s already exists, removing old androidtv_remote entry",
                old_entry.unique_id,
            )
            await hass.config_entries.async_remove(old_entry.entry_id)
            return

    # Create new config entry for androidtv domain via config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "migration"},
        data=new_data,
    )

    if result.get("type") != "create_entry":
        _LOGGER.error(
            "Failed to create androidtv entry for migrated device %s: %s",
            old_entry.title,
            result,
        )
        return

    new_entry = result.get("result")
    if new_entry:
        _LOGGER.debug(
            "Created new androidtv entry %s for migrated device",
            new_entry.entry_id,
        )

    # Remove the old androidtv_remote entry
    # Note: Entity and device migration happens automatically when the new entry
    # loads with the same unique_id - Home Assistant handles this
    await hass.config_entries.async_remove(old_entry.entry_id)
    _LOGGER.info(
        "Successfully migrated androidtv_remote entry '%s' to androidtv",
        old_entry.title,
    )


async def _async_setup_adb_entry(
    hass: HomeAssistant, entry: AndroidTVConfigEntry
) -> bool:
    """Set up Android TV via ADB connection."""
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

    async def async_close_connection(event: Event) -> None:
        """Close Android Debug Bridge connection on HA Stop."""
        await aftv.adb_close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )
    entry.async_on_unload(entry.add_update_listener(update_listener))

    entry.runtime_data = AndroidTVADBRuntimeData(aftv, entry.options.copy())

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_setup_remote_entry(
    hass: HomeAssistant, entry: AndroidTVConfigEntry
) -> bool:
    """Set up Android TV via Remote protocol connection."""
    _LOGGER.debug("async_setup_entry (remote): %s", entry.data)
    api = create_remote_api(
        hass, entry.data[CONF_HOST], get_enable_ime(entry.options)
    )

    @callback
    def is_available_updated(is_available: bool) -> None:
        _LOGGER.info(
            "%s %s at %s",
            "Reconnected to" if is_available else "Disconnected from",
            entry.data[CONF_NAME],
            entry.data[CONF_HOST],
        )

    api.add_is_available_updated_callback(is_available_updated)

    try:
        async with timeout(5.0):
            await api.async_connect()
    except InvalidAuth as exc:
        # The Android TV is hard reset or the certificate and key files were deleted.
        raise ConfigEntryAuthFailed from exc
    except (CannotConnect, ConnectionClosed, TimeoutError) as exc:
        # The Android TV is network unreachable. Raise exception and let Home Assistant retry
        # later. If device gets a new IP address the zeroconf flow will update the config.
        raise ConfigEntryNotReady from exc

    def reauth_needed() -> None:
        """Start a reauth flow if Android TV is hard reset while reconnecting."""
        entry.async_start_reauth(hass)

    # Start a task (canceled in disconnect) to keep reconnecting if device becomes
    # network unreachable. If device gets a new IP address the zeroconf flow will
    # update the config entry data and reload the config entry.
    api.keep_reconnecting(reauth_needed)

    entry.runtime_data = AndroidTVRemoteRuntimeData(api, entry.options.copy())

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def on_hass_stop(event: Event) -> None:
        """Stop push updates when hass stops."""
        api.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )
    entry.async_on_unload(api.disconnect)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_setup_entry(hass: HomeAssistant, entry: AndroidTVConfigEntry) -> bool:
    """Set up Android TV from a config entry."""
    connection_type = entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_ADB)

    if connection_type == CONNECTION_TYPE_REMOTE:
        return await _async_setup_remote_entry(hass, entry)
    return await _async_setup_adb_entry(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: AndroidTVConfigEntry) -> bool:
    """Unload a config entry."""
    connection_type = entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_ADB)

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        if connection_type == CONNECTION_TYPE_REMOTE:
            # Remote protocol - disconnect is handled by async_on_unload
            pass
        else:
            # ADB connection
            runtime_data = entry.runtime_data
            if isinstance(runtime_data, AndroidTVADBRuntimeData):
                await runtime_data.aftv.adb_close()

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: AndroidTVConfigEntry) -> None:
    """Update when config_entry options update."""
    connection_type = entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_ADB)
    runtime_data = entry.runtime_data

    if connection_type == CONNECTION_TYPE_ADB and isinstance(
        runtime_data, AndroidTVADBRuntimeData
    ):
        reload_opt = False
        old_options = runtime_data.dev_opt
        for opt_key, opt_val in entry.options.items():
            if opt_key in RELOAD_OPTIONS:
                old_val = old_options.get(opt_key)
                if old_val is None or old_val != opt_val:
                    reload_opt = True
                    break

        if reload_opt:
            await hass.config_entries.async_reload(entry.entry_id)
            return

        runtime_data.dev_opt = entry.options.copy()
        async_dispatcher_send(hass, f"{SIGNAL_CONFIG_ENTITY}_{entry.entry_id}")
    else:
        # For remote protocol, always reload on options change
        await hass.config_entries.async_reload(entry.entry_id)
