"""Platform for the iZone AC."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EXCLUDE, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import discovery
from .const import DATA_CONFIG, DOMAIN

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
    if conf := config.get(DOMAIN):
        hass.data[DATA_CONFIG] = conf

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    try:
        await discovery.async_start_discovery_service(hass)
    except OSError as err:
        raise ConfigEntryNotReady("iZone discovery service failed to start") from err

    if entry.unique_id == DOMAIN:
        # Legacy v1-migrated entry: resolve to a real controller UID at setup time.
        #
        # Doing this work here (rather than in async_migrate_entry) is intentional:
        # ConfigEntryNotReady raised from async_migrate_entry becomes a permanent
        # MIGRATION_ERROR — HA does not retry failed migrations.  Raising it from
        # async_setup_entry correctly schedules a retry on the next HA start.
        #
        # Raising ConfigEntryError (multiple eligible controllers) is permanent either
        # way; those controllers are not lost — the discovery fan-out will surface them
        # as individual flows once HA restarts.  This is not a breaking change: a v1
        # entry with multiple controllers was already broken before this PR.
        # async_discover_controllers reuses the already-running service (idempotent
        # start), so OSError here means fetch_controllers() itself failed — rare but
        # kept as a defensive guard.
        try:
            controllers = await discovery.async_discover_controllers(hass)
        except OSError as err:
            raise ConfigEntryNotReady(
                "iZone discovery failed while resolving legacy config entry"
            ) from err

        conf: ConfigType | None = hass.data.get(DATA_CONFIG)
        excluded_uids: set[str] = set(conf.get(CONF_EXCLUDE, [])) if conf else set()
        configured_uids = {
            config_entry.unique_id
            for config_entry in hass.config_entries.async_entries(DOMAIN)
            if config_entry.entry_id != entry.entry_id
            and config_entry.unique_id not in (None, DOMAIN)
        }
        eligible = [
            controller
            for controller in controllers.values()
            if controller.device_uid not in excluded_uids
            and controller.device_uid not in configured_uids
        ]

        if not eligible:
            raise ConfigEntryNotReady(
                "No eligible iZone controller found to bind to legacy config entry"
            )

        if len(eligible) > 1:
            raise ConfigEntryError(
                "Multiple eligible iZone controllers found for a legacy config entry; "
                "delete this entry and re-add each controller individually"
            )

        controller = eligible[0]
        new_title = (
            f"iZone {controller.device_uid}"
            if entry.title == "iZone Aircon"
            else entry.title
        )
        hass.config_entries.async_update_entry(
            entry,
            unique_id=controller.device_uid,
            title=new_title,
            data={CONF_HOST: controller.device_ip},
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entry schema to the current version."""
    if entry.version == 1:
        # Clear legacy data only — UID and title binding is deferred to
        # async_setup_entry where ConfigEntryNotReady retry semantics work correctly.
        # Raising ConfigEntryNotReady from async_migrate_entry would permanently land
        # the entry in MIGRATION_ERROR with no retry path.
        hass.config_entries.async_update_entry(entry, version=2, data={})
        return True
    return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
