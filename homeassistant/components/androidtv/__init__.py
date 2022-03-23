"""Support for functionality to interact with Android TV/Fire TV devices."""
import logging
import os

from adb_shell.auth.keygen import keygen
from androidtv.adb_manager.adb_manager_sync import ADBPythonSync
from androidtv.setup_async import setup

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import ConfigType

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
    PROP_SERIALNO,
    PROP_WIFIMAC,
    SIGNAL_CONFIG_ENTITY,
)

PLATFORMS = [Platform.MEDIA_PLAYER]
RELOAD_OPTIONS = [CONF_STATE_DETECTION_RULES]

_INVALID_MACS = {"ff:ff:ff:ff:ff:ff"}

_LOGGER = logging.getLogger(__name__)


def get_androidtv_mac(dev_props):
    """Return formatted mac from device properties."""
    for prop_mac in (PROP_ETHMAC, PROP_WIFIMAC):
        if if_mac := dev_props.get(prop_mac):
            mac = format_mac(if_mac)
            if mac not in _INVALID_MACS:
                return mac
    return None


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


async def async_connect_androidtv(
    hass, config, *, state_detection_rules=None, timeout=30.0
):
    """Connect to Android device."""
    address = f"{config[CONF_HOST]}:{config[CONF_PORT]}"

    adbkey, signer, adb_log = await hass.async_add_executor_job(
        _setup_androidtv, hass, config
    )

    aftv = await setup(
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
            device_name = "Android TV device"
        elif config[CONF_DEVICE_CLASS] == DEVICE_FIRETV:
            device_name = "Fire TV device"
        else:
            device_name = "Android TV / Fire TV device"

        error_message = f"Could not connect to {device_name} at {address} {adb_log}"
        return None, error_message

    return aftv, None


def _migrate_aftv_entity(hass, aftv, entry_unique_id):
    """Migrate a entity to new unique id."""
    entity_reg = er.async_get(hass)

    entity_unique_id = entry_unique_id
    if entity_reg.async_get_entity_id(MP_DOMAIN, DOMAIN, entity_unique_id):
        # entity already exist, nothing to do
        return

    if not (old_unique_id := aftv.device_properties.get(PROP_SERIALNO)):
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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Android TV integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Android TV platform."""

    state_det_rules = entry.options.get(CONF_STATE_DETECTION_RULES)
    aftv, error_message = await async_connect_androidtv(
        hass, entry.data, state_detection_rules=state_det_rules
    )
    if not aftv:
        raise ConfigEntryNotReady(error_message)

    # migrate existing entity to new unique ID
    if entry.source == SOURCE_IMPORT:
        _migrate_aftv_entity(hass, aftv, entry.unique_id)

    async def async_close_connection(event):
        """Close Android TV connection on HA Stop."""
        await aftv.adb_close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )
    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        ANDROID_DEV: aftv,
        ANDROID_DEV_OPT: entry.options.copy(),
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

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
