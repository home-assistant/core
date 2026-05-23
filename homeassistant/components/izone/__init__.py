"""Platform for the iZone AC."""

import pizone
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EXCLUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import config_flow
from .const import DATA_CONFIG, IZONE
from .discovery import async_start_discovery_service

PLATFORMS = [Platform.CLIMATE]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_EXCLUDE, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the iZone component config."""
    if conf := config.get(IZONE):
        hass.data[DATA_CONFIG] = conf

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def _async_pick_legacy_migration_controller(
    hass: HomeAssistant, entry: ConfigEntry
) -> pizone.Controller:
    """Return the single controller to bind to a legacy ``unique_id == izone`` entry.

    Raises ConfigEntryNotReady if no eligible controller is found on the network,
    or ConfigEntryError if multiple eligible controllers are found (ambiguous).
    """
    try:
        controllers = await config_flow.async_discover_controllers(hass)
    except OSError:
        raise ConfigEntryNotReady("iZone discovery service failed to start") from None
    conf: ConfigType | None = hass.data.get(DATA_CONFIG)
    excluded_uids: set[str] = set(conf[CONF_EXCLUDE]) if conf else set()
    configured_uids = {
        config_entry.unique_id
        for config_entry in hass.config_entries.async_entries(IZONE)
        if config_entry.entry_id != entry.entry_id
        and config_entry.unique_id not in (None, IZONE)
    }
    eligible = [
        controller
        for controller in controllers.values()
        if controller.device_uid not in excluded_uids
        and controller.device_uid not in configured_uids
    ]

    if not eligible:
        raise ConfigEntryNotReady(
            "No eligible iZone controller found to migrate legacy config entry"
        )

    if len(eligible) > 1:
        raise ConfigEntryError(
            "Multiple eligible iZone controllers found for a legacy config entry"
        )

    return eligible[0]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    try:
        await async_start_discovery_service(hass)
    except OSError as err:
        raise ConfigEntryNotReady("iZone discovery service failed to start") from err
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entry schema to the current version."""
    if entry.version == 1:
        controller = await _async_pick_legacy_migration_controller(hass, entry)
        new_title = (
            f"iZone {controller.device_uid}"
            if entry.title == "iZone Aircon"
            else entry.title
        )
        hass.config_entries.async_update_entry(
            entry,
            version=2,
            unique_id=controller.device_uid,
            data={},
            title=new_title,
        )
        return True
    return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
