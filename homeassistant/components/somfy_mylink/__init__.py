"""Component for the Somfy MyLink device supporting the Synergy API."""
import asyncio
import logging

from somfy_mylink_synergy import SomfyMyLinkSynergy
import voluptuous as vol

from homeassistant.components.cover import ENTITY_ID_FORMAT
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.util import slugify

from .const import (
    CONF_DEFAULT_REVERSE,
    CONF_ENTITY_CONFIG,
    CONF_REVERSE,
    CONF_REVERSED_TARGET_IDS,
    CONF_SYSTEM_ID,
    DATA_SOMFY_MYLINK,
    DEFAULT_PORT,
    DOMAIN,
    MYLINK_STATUS,
    PLATFORMS,
)

CONFIG_OPTIONS = (CONF_DEFAULT_REVERSE, CONF_ENTITY_CONFIG)
UNDO_UPDATE_LISTENER = "undo_update_listener"

_LOGGER = logging.getLogger(__name__)


def validate_entity_config(values):
    """Validate config entry for CONF_ENTITY."""
    entity_config_schema = vol.Schema({vol.Optional(CONF_REVERSE): cv.boolean})
    if not isinstance(values, dict):
        raise vol.Invalid("expected a dictionary")
    entities = {}
    for entity_id, config in values.items():
        entity = cv.entity_id(entity_id)
        config = entity_config_schema(config)
        entities[entity] = config
    return entities


CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_SYSTEM_ID): cv.string,
                    vol.Required(CONF_HOST): cv.string,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                    vol.Optional(CONF_DEFAULT_REVERSE, default=False): cv.boolean,
                    vol.Optional(
                        CONF_ENTITY_CONFIG, default={}
                    ): validate_entity_config,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the MyLink platform."""

    conf = config.get(DOMAIN)
    hass.data.setdefault(DOMAIN, {})

    if not conf:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Somfy MyLink from a config entry."""
    _async_import_options_from_data_if_missing(hass, entry)

    config = entry.data
    somfy_mylink = SomfyMyLinkSynergy(
        config[CONF_SYSTEM_ID], config[CONF_HOST], config[CONF_PORT]
    )

    try:
        mylink_status = await somfy_mylink.status_info()
    except asyncio.TimeoutError as ex:
        raise ConfigEntryNotReady(
            "Unable to connect to the Somfy MyLink device, please check your settings"
        ) from ex

    if not mylink_status or "error" in mylink_status:
        _LOGGER.error(
            "Somfy Mylink failed to setup because of an error: %s",
            mylink_status.get("error", {}).get(
                "message", "Empty response from mylink device"
            ),
        )
        return False

    if "result" not in mylink_status:
        raise ConfigEntryNotReady("The Somfy MyLink device returned an empty result")

    _async_migrate_entity_config(hass, entry, mylink_status)

    undo_listener = entry.add_update_listener(_async_update_listener)

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_SOMFY_MYLINK: somfy_mylink,
        MYLINK_STATUS: mylink_status,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


@callback
def _async_import_options_from_data_if_missing(hass: HomeAssistant, entry: ConfigEntry):
    options = dict(entry.options)
    data = dict(entry.data)
    modified = False

    for importable_option in CONFIG_OPTIONS:
        if importable_option not in options and importable_option in data:
            options[importable_option] = data.pop(importable_option)
            modified = True

    if modified:
        hass.config_entries.async_update_entry(entry, data=data, options=options)


@callback
def _async_migrate_entity_config(
    hass: HomeAssistant, entry: ConfigEntry, mylink_status: dict
):
    if CONF_ENTITY_CONFIG not in entry.options:
        return

    options = dict(entry.options)

    reversed_target_ids = options[CONF_REVERSED_TARGET_IDS] = {}
    legacy_entry_config = options[CONF_ENTITY_CONFIG]
    default_reverse = options.get(CONF_DEFAULT_REVERSE)

    for cover in mylink_status["result"]:
        legacy_entity_id = ENTITY_ID_FORMAT.format(slugify(cover["name"]))
        target_id = cover["targetID"]

        entity_config = legacy_entry_config.get(legacy_entity_id, {})
        if entity_config.get(CONF_REVERSE, default_reverse):
            reversed_target_ids[target_id] = True

    for legacy_key in (CONF_DEFAULT_REVERSE, CONF_ENTITY_CONFIG):
        if legacy_key in options:
            del options[legacy_key]

    hass.config_entries.async_update_entry(entry, data=entry.data, options=options)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    hass.data[DOMAIN][entry.entry_id][UNDO_UPDATE_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
