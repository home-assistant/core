"""Support for functionality to interact with AIS Android devices."""
import json
import logging
import os

from adb_shell.auth.keygen import keygen
from androidtv import state_detection_rules_validator
from androidtv.adb_manager.adb_manager_sync import ADBPythonSync
from androidtv.setup_async import setup

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
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
    MIGRATION_DATA,
    PROP_SERIALNO,
    SIGNAL_CONFIG_ENTITY,
)

PLATFORMS = [MP_DOMAIN]
RELOAD_OPTIONS = [CONF_STATE_DETECTION_RULES]

_LOGGER = logging.getLogger(__name__)


def _setup_androidtv(hass, config):
    """Generate an ADB key (if needed) and load it."""
    adbkey = config.get(CONF_ADBKEY, hass.config.path(STORAGE_DIR, "androidtv_adbkey"))
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
        adb_log = f"using ADB server at {config[CONF_ADB_SERVER_IP]}:{config[CONF_ADB_SERVER_PORT]}"

    return adbkey, signer, adb_log


def validate_state_det_rules(state_det_rules):
    """Validate a string that contain state detection rules and return a dict."""
    if not state_det_rules:
        return None

    try:
        json_rules = json.loads(state_det_rules)
    except ValueError:
        _LOGGER.warning("Error loading state detection rules")
        return None
    try:
        state_detection_rules_validator(json_rules, ValueError)
    except ValueError as exc:
        _LOGGER.warning("Invalid state detection rules: %s", exc)
        return None
    return json_rules


async def async_connect_androidtv(
    hass, config, *, state_detection_rules=None, timeout=30.0
):
    """Connect to Android device."""
    address = f"{config[CONF_HOST]}:{config[CONF_PORT]}"

    adbkey, signer, adb_log = await hass.async_add_executor_job(
        _setup_androidtv, hass, config
    )

    aftv = await setup(
        host=config[CONF_HOST],
        port=config[CONF_PORT],
        adbkey=adbkey,
        adb_server_ip=config.get(CONF_ADB_SERVER_IP),
        adb_server_port=config.get(CONF_ADB_SERVER_PORT, DEFAULT_ADB_SERVER_PORT),
        state_detection_rules=state_detection_rules,
        device_class=config[CONF_DEVICE_CLASS],
        auth_timeout_s=30.0,
        signer=signer,
    )

    if not aftv.available:
        # Determine the name that will be used for the device in the log
        if config[CONF_HOST] == "127.0.0.1":
            device_name = "Android AIS"
        elif config[CONF_DEVICE_CLASS] == DEVICE_ANDROIDTV:
            device_name = "Android device"
        elif config[CONF_DEVICE_CLASS] == DEVICE_FIRETV:
            device_name = "Fire TV device"
        else:
            device_name = "Android TV / Fire TV device"

        _LOGGER.warning(
            "Could not connect to %s at %s %s", device_name, address, adb_log
        )
        return None

    return aftv


def _migrate_aftv_entity(hass, aftv, entry_unique_id):
    """Migrate a entity to new unique id."""
    entity_reg = er.async_get(hass)

    entity_unique_id = entry_unique_id
    if entity_reg.async_get_entity_id(MP_DOMAIN, DOMAIN, entity_unique_id):
        # entity already exist, nothing to do
        return

    old_unique_id = aftv.device_properties.get(PROP_SERIALNO)
    if not old_unique_id:
        # serial no not found, exit
        return

    migr_entity = entity_reg.async_get_entity_id(MP_DOMAIN, DOMAIN, old_unique_id)
    if not migr_entity:
        # old entity not found, exit
        return

    try:
        entity_reg.async_update_entity(migr_entity, new_unique_id=entity_unique_id)
    except ValueError as exp:
        _LOGGER.warning("Migration of old entity failed: %s", exp)


async def async_setup(hass, config):
    """Set up the Android TV integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Android TV platform."""

    host = entry.data[CONF_HOST]

    # import options from migration if empty
    yaml_options = hass.data.get(DOMAIN, {}).get(MIGRATION_DATA, {}).pop(host, {})
    if not entry.options and yaml_options:
        hass.config_entries.async_update_entry(entry, options=yaml_options)

    state_det_rules = entry.options.get(CONF_STATE_DETECTION_RULES)
    json_rules = validate_state_det_rules(state_det_rules)

    aftv = await async_connect_androidtv(
        hass, entry.data, state_detection_rules=json_rules
    )
    if not aftv:
        raise ConfigEntryNotReady()

    # migrate existing entity to new unique ID
    if entry.source == SOURCE_IMPORT:
        _migrate_aftv_entity(hass, aftv, entry.unique_id)

    async def async_close_connection(event):
        """Close Android TV connection on HA Stop."""
        await aftv.adb_close()

    stop_listener = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, async_close_connection
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        ANDROID_DEV: aftv,
        ANDROID_DEV_OPT: entry.options.copy(),
        "conf_listener": entry.add_update_listener(update_listener),
        "stop_listener": stop_listener,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN][entry.entry_id]["stop_listener"]()
        hass.data[DOMAIN][entry.entry_id]["conf_listener"]()
        aftv = hass.data[DOMAIN][entry.entry_id][ANDROID_DEV]
        await aftv.adb_close()

        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
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
    else:
        hass.data[DOMAIN][entry.entry_id][ANDROID_DEV_OPT] = entry.options.copy()
        async_dispatcher_send(hass, f"{SIGNAL_CONFIG_ENTITY}_{entry.entry_id}")
