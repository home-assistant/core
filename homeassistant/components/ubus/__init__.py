"""The OpenWrt (ubus) integration."""

# pylint: disable=home-assistant-use-runtime-data  # The merge map is cross-entry state; entry.runtime_data is per-entry and is cleared by the hub reload a merge runs
import asyncio
import logging
from types import MappingProxyType

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigSubentry,
    UnknownEntry,
)
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import AnyDeviceEntry
from homeassistant.helpers.typing import ConfigType

from .config_flow import UbusConfigFlow
from .const import DOMAIN, SUBENTRY_TYPE_ROUTER
from .coordinator import UbusConfigEntry, UbusDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.DEVICE_TRACKER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OpenWrt (ubus) integration."""
    # Consolidate one-router-per-entry installs before any entry is set
    # up, so an entry the migration removes is never set up for.
    await _async_migrate(hass)
    return True


async def _async_entry_updated(hass: HomeAssistant, entry: UbusConfigEntry) -> None:
    """React to a change of the entry.

    Core does not reload an entry when its subentries are added, removed or
    changed, so a router change polls right away instead; an option change
    needs no poll, as the coordinator reads the options live and only the
    trackers need to be signalled.
    """
    coordinator: UbusDataUpdateCoordinator = entry.runtime_data
    if coordinator.subentries_changed():
        # Refresh right away; a debounced request can be discarded while a
        # tick holds the refresh lock.
        await coordinator.async_refresh()
        return
    coordinator.async_signal_clients_updated()


async def async_setup_entry(hass: HomeAssistant, entry: UbusConfigEntry) -> None:
    """Set up the OpenWrt (ubus) hub from a config entry."""
    # The startup consolidation may have run before a hub existed: a YAML
    # import creates one with every entry disabled, so this entry would
    # become a second poller unless it merges into the hub now. Only a
    # loaded hub holding routers is a target: one being set up or removed
    # may not stay and could merge in turn, and an empty shell left by a
    # failed migration is meant to be deleted. A merge into the hub reloads
    # it, so the hub is not loaded while the merge runs; a setup racing it
    # waits for the merge, or it would start a poller of its own.
    merging: dict[str, asyncio.Event] = hass.data.setdefault(DOMAIN, {})
    while True:
        hub = next(
            (
                candidate
                for candidate in hass.config_entries.async_entries(DOMAIN)
                if (
                    candidate is not entry
                    and (
                        candidate.state is ConfigEntryState.LOADED
                        or candidate.entry_id in merging
                    )
                    and candidate.disabled_by is None
                    and candidate.version <= UbusConfigFlow.VERSION
                    and not candidate.data
                    and candidate.subentries
                )
            ),
            None,
        )
        if hub is None or hub.entry_id not in merging:
            if hub is not None:
                merging[hub.entry_id] = asyncio.Event()
            break
        await merging[hub.entry_id].wait()
    if hub is not None:
        try:
            merged = await _async_migrate_other(
                hass, hub, entry, holding_setup_lock=True
            )
        finally:
            merging[hub.entry_id].set()
            del merging[hub.entry_id]
        if merged:
            return
    coordinator = UbusDataUpdateCoordinator(hass, entry)
    # A coordinator only polls while it has a listener; the entity updates
    # are driven by the presence signal, not by it.
    entry.async_on_unload(coordinator.async_add_listener(_async_keep_polling))
    # A router whose first poll fails does not fail entry setup: it is
    # marked unhealthy and polling continues until it recovers.
    await coordinator.async_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    issue_registry = ir.async_get(hass)
    for issue in list(issue_registry.issues.values()):
        if (
            issue.domain == DOMAIN
            and issue.config_entry_id == entry.entry_id
            and issue.translation_key == "migration_hub_reload_failed"
        ):
            ir.async_delete_issue(hass, DOMAIN, issue.issue_id)


def _async_keep_polling() -> None:
    """Keep the coordinator polling; the presence signal drives the updates."""


async def async_unload_entry(hass: HomeAssistant, entry: UbusConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: UbusConfigEntry, device_entry: AnyDeviceEntry
) -> bool:
    """Allow removing a client device which is not currently connected."""
    if not isinstance(device_entry, dr.DeviceEntry):
        # This integration does not create child devices.
        return False
    if config_entry.state is not ConfigEntryState.LOADED:
        return True
    coordinator: UbusDataUpdateCoordinator = config_entry.runtime_data
    return all(
        coordinator.latest_stamp(dr.format_mac(connection)) is None
        for connection_type, connection in device_entry.connections
        if connection_type == dr.CONNECTION_NETWORK_MAC
    )


def _async_convert_own_data(hass: HomeAssistant, entry: UbusConfigEntry) -> None:
    """Move this entry's own router data into a subentry, making it a pure hub.

    The entry is left on the hub schema version, so an older release
    rejects the empty-data hub instead of adopting it.
    """
    if entry.data:
        data = dict(entry.data)
        host = data[CONF_HOST]
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType(data),
                subentry_type=SUBENTRY_TYPE_ROUTER,
                title=host,
                unique_id=host,
            ),
        )
    hass.config_entries.async_update_entry(entry, data={}, version=2)


async def async_migrate_entry(hass: HomeAssistant, entry: UbusConfigEntry) -> None:
    """Migrate a version-1 entry to the hub-and-subentry schema."""
    _async_convert_own_data(hass, entry)


async def _async_migrate(hass: HomeAssistant) -> None:
    """Migrate a one-router-per-entry install to the hub-and-subentry model.

    The lowest-id entry becomes the hub, preferring an entry which is
    already on the hub schema so a leftover legacy entry cannot usurp an
    existing hub. The migration converts the hub's own router data into a
    subentry and re-parents every other entry (including disabled ones)
    into subentries, then removes those entries. It happens exactly once,
    in component setup, before any entry is set up.

    Entries on a schema newer than the config flow's version were written
    by a newer release; after a rollback this migration must not downgrade
    or remove them, so they are left in place.

    A disabled entry is never the hub. The hub's polling preference
    acts on every router, so it keeps polling when any entry polled on
    its own entry; a router whose entry had polling disabled starts
    polling, with a warning per subentry, the hub's own included.
    """
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.version <= UbusConfigFlow.VERSION
    ]
    hub_candidates = [e for e in entries if e.disabled_by is None]
    if not hub_candidates:
        return
    hubs = [e for e in hub_candidates if not e.data]
    populated_hubs = [e for e in hubs if e.subentries]
    hub = min(populated_hubs or hubs or hub_candidates, key=lambda e: e.entry_id)
    # Polling is one entry-level preference, so the hub keeps polling
    # when any entry polled on its own entry; an entry which did not
    # poll starts polling, warned per subentry.
    polling_reconciled = False
    if hub.pref_disable_polling and any(
        not candidate.pref_disable_polling for candidate in hub_candidates
    ):
        hass.config_entries.async_update_entry(hub, pref_disable_polling=False)
        polling_reconciled = True
    _async_convert_own_data(hass, hub)
    if polling_reconciled:
        # The flip also starts polling for the hub's own routers,
        # which the transferred-entry warnings below do not reach.
        for subentry in hub.subentries.values():
            _async_create_polling_enabled_issue(hass, hub, subentry)
    for other in sorted((e for e in entries if e is not hub), key=lambda e: e.entry_id):
        await _async_migrate_other(hass, hub, other)


@callback
def _async_transfer_to_hub(
    hass: HomeAssistant,
    hub: UbusConfigEntry,
    entry: ConfigEntry,
) -> list[str]:
    """Re-parent this entry's trackers and routers to the hub, then empty it.

    A host collision only skips the colliding router; the remaining
    routers are still transferred. Returns the colliding hosts.
    """
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    _async_reparent(hub, entry, device_registry, entity_registry)
    collision_hosts: list[str] = []
    created_subentries: list[ConfigSubentry] = []
    for subentry in entry.subentries.values():
        new_subentry = ConfigSubentry(
            data=MappingProxyType(dict(subentry.data)),
            subentry_type=SUBENTRY_TYPE_ROUTER,
            title=subentry.title,
            unique_id=subentry.unique_id,
        )
        try:
            hass.config_entries.async_add_subentry(hub, new_subentry)
        except AbortFlow:
            # A host collision: the hub keeps its copy of this
            # router, and the remaining routers are still
            # transferred below.
            collision_hosts.append(subentry.title)
        else:
            created_subentries.append(new_subentry)
    if entry.data:
        data = dict(entry.data)
        new_subentry = ConfigSubentry(
            data=MappingProxyType(data),
            subentry_type=SUBENTRY_TYPE_ROUTER,
            title=data[CONF_HOST],
            unique_id=data[CONF_HOST],
        )
        try:
            hass.config_entries.async_add_subentry(hub, new_subentry)
        except AbortFlow:
            collision_hosts.append(data[CONF_HOST])
        else:
            created_subentries.append(new_subentry)
    # Subentries cannot be disabled or set to not poll, so a router
    # whose entry had either off starts being polled by the hub;
    # deleting the subentry reproduces the old behavior, and clears
    # the warning which is linked to it. A colliding host has no new
    # subentry, so there is nothing to delete.
    if entry.disabled_by is not None:
        for created in created_subentries:
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"migration_disabled_entry_{created.subentry_id}",
                config_entry_id=hub.entry_id,
                config_subentry_id=created.subentry_id,
                is_fixable=False,
                is_persistent=True,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key="migration_disabled_entry",
                translation_placeholders={"host": created.title},
            )
    elif entry.pref_disable_polling and not hub.pref_disable_polling:
        for created in created_subentries:
            _async_create_polling_enabled_issue(hass, hub, created)
    # The entry is a shell now: its routers are tracked on the hub,
    # so clearing its subentries and data means a failed removal
    # cannot leave a duplicate poller behind.
    for subentry in list(entry.subentries.values()):
        hass.config_entries.async_remove_subentry(entry, subentry.subentry_id)
    hass.config_entries.async_update_entry(entry, data={}, version=2)
    return collision_hosts


async def _async_migrate_other(
    hass: HomeAssistant,
    hub: UbusConfigEntry,
    entry: ConfigEntry,
    holding_setup_lock: bool = False,
) -> bool:
    """Re-parent a legacy entry into subentries of the hub and remove it.

    An entry which cannot be unloaded is left in place, untouched, so its
    router keeps polling on its own entry. Once its routers are tracked
    on the hub, the entry is emptied before removal, so a failed removal
    leaves a shell which cannot poll the same routers again and is
    removed by the next migration; its repair points at deleting it. A
    host collision only skips the colliding router; the remaining
    routers are still transferred. The hub setup is never blocked by
    one un-migratable entry.

    With holding_setup_lock the entry is being set up under the core-held
    setup lock and was never loaded, so it is transferred in place and
    removed by a task which runs once the setup lock is released. Returns
    whether the entry was merged; the caller sets the entry up normally
    when it was not.
    """
    # An entry set up before the migration converted its own data into a
    # subentry, so the host lives in the subentry title then.
    host = entry.data.get(CONF_HOST)
    if host is None:
        host = (
            next(iter(entry.subentries.values())).title
            if entry.subentries
            else entry.entry_id
        )
    transferred = False
    try:
        if holding_setup_lock:
            if hub.pref_disable_polling and not entry.pref_disable_polling:
                hass.config_entries.async_update_entry(hub, pref_disable_polling=False)
                for subentry in hub.subentries.values():
                    _async_create_polling_enabled_issue(hass, hub, subentry)
            collision_hosts = _async_transfer_to_hub(hass, hub, entry)
            transferred = True
            # The hub already normalized its own tracker ids, before
            # the merge moved this entry's over; reload it so the
            # merged ids are normalized too, not left as duplicates.
            # async_reload returns False instead of raising on a
            # failed unload or setup.
            if not await hass.config_entries.async_reload(hub.entry_id):
                _async_create_hub_reload_failed_issue(hass, hub, entry, host)
            # The removal needs the setup lock, which is held for the
            # rest of the setup, so it runs in a deferred task.
            hass.async_create_task(_async_deferred_removal(hass, hub, entry, host))
        else:
            # Hold the entry's setup lock so it is never removed mid-setup and
            # no setup can start while it is unloaded.
            async with entry.setup_lock:
                if (
                    not entry.state.recoverable
                    or not await hass.config_entries.async_unload(
                        entry.entry_id, _lock=False
                    )
                ):
                    _LOGGER.warning(
                        "Could not unload ubus entry %s; leaving it in place "
                        "instead of migrating it to the hub",
                        entry.entry_id,
                    )
                    ir.async_create_issue(
                        hass,
                        DOMAIN,
                        f"migration_failed_{entry.entry_id}",
                        config_entry_id=entry.entry_id,
                        is_fixable=False,
                        issue_domain=DOMAIN,
                        severity=ir.IssueSeverity.ERROR,
                        translation_key="migration_failed",
                        translation_placeholders={"host": host},
                    )
                    return False
                collision_hosts = _async_transfer_to_hub(hass, hub, entry)
            transferred = True
            # The entry was unloaded above, so the removal cannot leave live
            # trackers behind.
            await hass.config_entries.async_remove(entry.entry_id)
        if collision_hosts:
            _LOGGER.warning(
                "Host %s already exists on the hub; removing the duplicate ubus entry",
                ", ".join(collision_hosts),
            )
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"migration_host_collision_{entry.entry_id}",
                is_fixable=False,
                is_persistent=True,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key="migration_host_collision",
                translation_placeholders={"host": ", ".join(collision_hosts)},
            )
    except HomeAssistantError:
        # Only expected core failures become repairs; any other
        # exception is a bug and must surface.
        _LOGGER.exception(
            "Failed to migrate ubus entry %s to the hub %s",
            entry.entry_id,
            hub.entry_id,
        )
        if transferred:
            _async_create_removal_failed_issue(hass, entry, host)
        else:
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"migration_failed_{entry.entry_id}",
                config_entry_id=entry.entry_id,
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.ERROR,
                translation_key="migration_failed",
                translation_placeholders={"host": host},
            )
        return False
    return True


@callback
def _async_create_hub_reload_failed_issue(
    hass: HomeAssistant, hub: UbusConfigEntry, entry: ConfigEntry, host: str
) -> None:
    """Create the repair for a hub which could not be reloaded after a merge.

    The merged entry is an empty shell which is removed anyway, and
    issues are cleared with their entry, so the repair is tied to the
    hub, which keeps the moved data.
    """
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"migration_hub_reload_failed_{entry.entry_id}",
        config_entry_id=hub.entry_id,
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.ERROR,
        translation_key="migration_hub_reload_failed",
        translation_placeholders={"host": host},
    )


@callback
def _async_create_removal_failed_issue(
    hass: HomeAssistant, entry: ConfigEntry, host: str
) -> None:
    """Create the repair for a merged entry which could not be removed.

    The leftover entry is an empty shell now, so the repair can point
    at deleting it.
    """
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"migration_removal_failed_{entry.entry_id}",
        config_entry_id=entry.entry_id,
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.ERROR,
        translation_key="migration_removal_failed",
        translation_placeholders={"host": host},
    )


@callback
def _async_create_polling_enabled_issue(
    hass: HomeAssistant,
    hub: UbusConfigEntry,
    subentry: ConfigSubentry,
) -> None:
    """Warn that this subentry's router starts polling on the hub.

    A subentry cannot carry a polling preference, so the warning is
    the only record of the router's previous off state; deleting the
    subentry reproduces it and clears the warning.
    """
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"migration_polling_enabled_{subentry.subentry_id}",
        config_entry_id=hub.entry_id,
        config_subentry_id=subentry.subentry_id,
        is_fixable=False,
        is_persistent=True,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="migration_polling_enabled",
        translation_placeholders={"host": subentry.title},
    )


async def _async_deferred_removal(
    hass: HomeAssistant, hub: ConfigEntry, entry: ConfigEntry, host: str
) -> None:
    """Remove a merged entry once its setup lock is released.

    The removal runs in a task because the setup lock is held for the
    rest of the setup; an unexpected failure cannot reach the
    migration handler, so it surfaces as a task error.
    """
    try:
        await hass.config_entries.async_remove(entry.entry_id)
    except UnknownEntry:
        # The entry was already removed; nothing is left to repair.
        return


def _merge_device_survivors(
    device: dr.DeviceEntry, target_device: dr.DeviceEntry
) -> tuple[dr.DeviceEntry, dr.DeviceEntry]:
    """Return the device to keep and the one to merge into it.

    A device the user named or placed in an area is established over the
    other; otherwise the older one wins, so its id, name, area and
    automation references survive the merge.
    """
    legacy_established = device.name_by_user is not None or device.area_id is not None
    hub_established = (
        target_device.name_by_user is not None or target_device.area_id is not None
    )
    derived_disabled = (None, dr.DeviceEntryDisabler.CONFIG_ENTRY)
    legacy_disabled = device.disabled_by not in derived_disabled
    hub_disabled = target_device.disabled_by not in derived_disabled
    if legacy_disabled != hub_disabled:
        survivor = target_device if legacy_disabled else device
    elif legacy_established != hub_established:
        survivor = device if legacy_established else target_device
    elif device.created_at <= target_device.created_at:
        survivor = device
    else:
        survivor = target_device
    return survivor, target_device if survivor is device else device


@callback
def _async_reparent(
    hub: UbusConfigEntry,
    entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Re-parent this entry's trackers and devices to the hub.

    Trackers are re-homed before any device moves: moving a device to
    another entry deletes the old entry's registry entries linked to it.
    Devices are found from the device registry, so a device whose tracker
    was deleted moves too and is not lost with the entry's removal.
    """
    for registry_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if (
            registry_entry.domain != DEVICE_TRACKER_DOMAIN
            or registry_entry.platform != DOMAIN
            or registry_entry.unique_id is None
        ):
            continue
        entity_registry.async_update_entity(
            registry_entry.entity_id, config_entry_id=hub.entry_id
        )
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        target_device: dr.DeviceEntry | None = None
        for connection_type, connection in device.connections:
            if connection_type != dr.CONNECTION_NETWORK_MAC:
                continue
            target_device = device_registry.async_get_device_by_connection(
                (dr.CONNECTION_NETWORK_MAC, connection), hub.entry_id
            )
        if target_device is None:
            device_registry.async_update_device(
                device.id, new_config_entry_id=hub.entry_id
            )
            continue
        survivor, loser = _merge_device_survivors(device, target_device)
        # Merge the losing device into the surviving one, including the
        # disabled entities only the losing one holds.
        for device_entry in er.async_entries_for_device(
            entity_registry, loser.id, include_disabled_entities=True
        ):
            entity_registry.async_update_entity(
                device_entry.entity_id, device_id=survivor.id
            )
        device_registry.async_remove_device(loser.id)
        if survivor is device:
            # The entry removal would delete the device otherwise.
            device_registry.async_update_device(
                device.id, new_config_entry_id=hub.entry_id
            )
