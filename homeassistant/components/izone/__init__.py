"""The iZone integration."""

import pizone
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EXCLUDE, CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DATA_CONFIG, DOMAIN
from .coordinator import IZoneConfigEntry, IZoneCoordinator
from .discovery import (
    async_discover_all_endpoints,
    async_discover_endpoint,
    async_ensure_discovery,
    async_stop_discovery,
    yaml_excluded_uids,
)

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


async def async_setup_entry(hass: HomeAssistant, entry: IZoneConfigEntry) -> bool:
    """Set up from a config entry."""
    try:
        discovery = await async_ensure_discovery(hass)
    except (OSError, RuntimeError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="discovery_start_failed",
        ) from err

    # Heal legacy / host-less entries here (not in migrate) so ConfigEntryNotReady
    # can retry. Upstream pairs migrate→data={} with this setup-time rebind.
    if entry.unique_id == DOMAIN:
        try:
            endpoints = await async_discover_all_endpoints(hass)
        except OSError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="discovery_failed_legacy",
            ) from err

        excluded_uids = yaml_excluded_uids(hass)
        configured_uids = {
            config_entry.unique_id
            for config_entry in hass.config_entries.async_entries(DOMAIN)
            if config_entry.entry_id != entry.entry_id
            and config_entry.unique_id not in (None, DOMAIN)
        }
        eligible = [
            endpoint
            for endpoint in endpoints.values()
            if endpoint.uid not in excluded_uids and endpoint.uid not in configured_uids
        ]

        if not eligible:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="no_eligible_controller",
            )

        if len(eligible) > 1:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="multiple_eligible_controllers",
            )

        endpoint = eligible[0]
        new_title = (
            f"iZone {endpoint.uid}" if entry.title == "iZone Aircon" else entry.title
        )
        hass.config_entries.async_update_entry(
            entry,
            unique_id=endpoint.uid,
            title=new_title,
            data={CONF_HOST: endpoint.host},
        )
    elif CONF_HOST not in entry.data:
        uid = entry.unique_id
        if not isinstance(uid, str):
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="missing_unique_id",
            )
        try:
            resolved = await async_discover_endpoint(hass, uid)
        except OSError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="discovery_failed_host",
            ) from err
        if resolved is None:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="controller_not_found",
                translation_placeholders={"uid": uid},
            )
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_HOST: resolved.host},
        )

    uid = entry.unique_id
    if not isinstance(uid, str):
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="missing_unique_id",
        )
    if CONF_HOST not in entry.data:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="missing_host",
        )

    host: str = entry.data[CONF_HOST]

    @callback
    def _async_on_address_changed(endpoint: pizone.ControllerEndpoint) -> None:
        if endpoint.host == entry.data[CONF_HOST]:
            return
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_HOST: endpoint.host},
        )

    try:
        controller = await discovery.create_controller(
            uid,
            host,
            on_address_changed=_async_on_address_changed,
        )
    except pizone.UnpairedBridgeError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="bridge_unpaired",
        ) from err
    except ConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": host},
        ) from err
    except pizone.ControllerCommandError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="setup_rejected",
            translation_placeholders={"host": host},
        ) from err

    entry.async_on_unload(controller.close)

    coordinator = IZoneCoordinator(hass, entry, controller)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: IZoneConfigEntry) -> bool:
    """Migrate old config entry schema to the current version."""
    if entry.version == 1:
        # Clear legacy data only.
        # Raising ConfigEntryNotReady from async_migrate_entry would permanently land
        # the entry in MIGRATION_ERROR with no retry path.
        hass.config_entries.async_update_entry(entry, version=2, data={})
        return True
    return False


async def async_unload_entry(hass: HomeAssistant, entry: IZoneConfigEntry) -> bool:
    """Unload the config entry and release the controller."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = entry.runtime_data
        await coordinator.async_shutdown()
        await coordinator.controller.close()
        if not hass.config_entries.async_loaded_entries(DOMAIN):
            await async_stop_discovery(hass)
    return unload_ok
