"""The iZone integration."""

import logging

import pizone
import probatio

from homeassistant import config_entries
from homeassistant.const import CONF_EXCLUDE, CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import IZoneConfigEntry, IZoneCoordinator
from .discovery import (
    async_discover_endpoint,
    async_ensure_discovery,
    async_stop_discovery,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

LEGACY_ENTRY_REMOVED_ISSUE_ID = "legacy_entry_removed"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
]

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Optional(CONF_EXCLUDE, default=[]): probatio.All(
                    probatio.EnsureList(), [cv.string]
                )
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the iZone component config."""
    async_setup_services(hass)
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.unique_id != DOMAIN:
            continue
        if entry.source == config_entries.SOURCE_IGNORE:
            # Pre-2026.8 HomeKit discovery ignores; they never migrate and match nothing.
            await hass.config_entries.async_remove(entry.entry_id)
        else:
            await _async_resolve_legacy_entry(hass, entry)

    if conf := config.get(DOMAIN):
        if conf[CONF_EXCLUDE]:
            ir.async_create_issue(
                hass,
                DOMAIN,
                "yaml_exclude_unused",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="yaml_exclude_unused",
            )

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: IZoneConfigEntry) -> None:
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
    if (host := entry.data.get(CONF_HOST)) is None:
        # Entries upgraded from before 2026.11 may not have a host yet.
        try:
            endpoint = await async_discover_endpoint(hass, uid)
        except pizone.EndpointVerifyError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"host": err.host},
            ) from err
        except (OSError, RuntimeError) as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="discovery_failed_host",
            ) from err
        if endpoint is None:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="controller_not_found",
                translation_placeholders={"uid": uid},
            )
        host = endpoint.host
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_HOST: host}
        )

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
    own_identifiers = {
        (DOMAIN, controller.device_uid),
        *((DOMAIN, controller.device_uid, zone.index) for zone in controller.zones),
    }
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if device.identifiers.isdisjoint(own_identifiers):
            device_registry.async_remove_device(device.id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Platforms set up concurrently; re-push so controller climate can
    # resolve zone entity_ids for control_zone_source after that gather.
    coordinator.async_set_updated_data(controller)

    issue = ir.async_get(hass).async_get_issue(DOMAIN, LEGACY_ENTRY_REMOVED_ISSUE_ID)
    if issue is not None and issue.data and uid in str(issue.data["uids"]).split(","):
        ir.async_delete_issue(hass, DOMAIN, LEGACY_ENTRY_REMOVED_ISSUE_ID)


async def async_migrate_entry(hass: HomeAssistant, entry: IZoneConfigEntry) -> None:
    """Migrate old config entry schema to the current version."""
    hass.config_entries.async_update_entry(entry, version=2, minor_version=2)


async def _async_resolve_legacy_entry(
    hass: HomeAssistant, entry: IZoneConfigEntry
) -> None:
    """Bind a pre-2026.8 entry to the controller its devices were registered under.

    Entries with no such controller, or several, can't be bound and are removed.
    """
    uids = {
        identifier[1]
        for device in dr.async_entries_for_config_entry(
            dr.async_get(hass), entry.entry_id
        )
        for identifier in device.identifiers
        if len(identifier) == 2 and identifier[0] == DOMAIN
    } or {
        entity.unique_id
        for entity in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if entity.domain == Platform.CLIMATE and "_" not in entity.unique_id
    }
    uids -= {
        other.unique_id
        for other in hass.config_entries.async_entries(DOMAIN, include_ignore=False)
        if other.entry_id != entry.entry_id
    }

    if len(uids) == 1:
        uid = uids.pop()
        # The working legacy entry wins over a later Ignore of its own controller.
        if ignored := hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, uid):
            await hass.config_entries.async_remove(ignored.entry_id)
        hass.config_entries.async_update_entry(
            entry,
            unique_id=uid,
            title=f"iZone {uid}" if entry.title == "iZone Aircon" else entry.title,
            data={},
            version=2,
            minor_version=2,
        )
        return

    await hass.config_entries.async_remove(entry.entry_id)
    if not uids:
        _LOGGER.info("Removed legacy iZone entry %s with no controller", entry.title)
        return

    _LOGGER.warning(
        "Removed legacy iZone entry %s registered to several controllers: %s",
        entry.title,
        ", ".join(sorted(uids)),
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        LEGACY_ENTRY_REMOVED_ISSUE_ID,
        data={"uids": ",".join(sorted(uids))},
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=LEGACY_ENTRY_REMOVED_ISSUE_ID,
        translation_placeholders={"uids": ", ".join(sorted(uids))},
    )


async def async_unload_entry(hass: HomeAssistant, entry: IZoneConfigEntry) -> None:
    """Unload the config entry and release the controller."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    coordinator = entry.runtime_data
    await coordinator.async_shutdown()
    await coordinator.controller.close()
    if not hass.config_entries.async_loaded_entries(DOMAIN):
        await async_stop_discovery(hass)
