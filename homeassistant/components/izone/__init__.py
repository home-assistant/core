"""The iZone integration."""

import pizone
import probatio

from homeassistant import config_entries
from homeassistant.const import CONF_EXCLUDE, CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
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

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Optional(CONF_EXCLUDE, default=[]): probatio.All(
                    cv.ensure_list, [cv.string]
                )
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
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

    # Register the controller device before forwarding platforms so zone
    # entities can resolve their via_device_id parent at construction time.
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, controller.device_uid)},
        manufacturer="IZone",
        model=controller.sys_type,
        name=f"iZone Controller {controller.device_uid}",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: IZoneConfigEntry) -> bool:
    """Migrate old config entry schema to the current version.

    Discovery for legacy ``unique_id=DOMAIN`` / missing ``CONF_HOST`` runs here so
    ``ConfigEntryNotReady`` can retry during migration.
    """
    if entry.version < 2 or entry.minor_version < 2:
        unique_id = entry.unique_id
        title = entry.title
        data = dict(entry.data)

        if unique_id == DOMAIN:
            try:
                endpoints = await async_discover_all_endpoints(hass)
            except (OSError, RuntimeError) as err:
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
                if endpoint.uid not in excluded_uids
                and endpoint.uid not in configured_uids
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
            unique_id = endpoint.uid
            if title == "iZone Aircon":
                title = f"iZone {endpoint.uid}"
            data = {CONF_HOST: endpoint.host}
        elif CONF_HOST not in data:
            if not isinstance(unique_id, str):
                raise ConfigEntryError(
                    translation_domain=DOMAIN,
                    translation_key="missing_unique_id",
                )
            try:
                resolved = await async_discover_endpoint(hass, unique_id)
            except (OSError, RuntimeError) as err:
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="discovery_failed_host",
                ) from err
            if resolved is None:
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="controller_not_found",
                    translation_placeholders={"uid": unique_id},
                )
            data = {**data, CONF_HOST: resolved.host}

        hass.config_entries.async_update_entry(
            entry,
            version=2,
            minor_version=2,
            unique_id=unique_id,
            title=title,
            data=data,
        )

    return True


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
