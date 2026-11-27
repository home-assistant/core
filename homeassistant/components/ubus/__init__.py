"""The OpenWrt (ubus) integration."""

import logging
from types import MappingProxyType

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigSubentry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import AnyDeviceEntry
from homeassistant.helpers.typing import ConfigType

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
        await coordinator.async_request_refresh()
        return
    coordinator.async_signal_clients_updated()


async def async_setup_entry(hass: HomeAssistant, entry: UbusConfigEntry) -> None:
    """Set up the OpenWrt (ubus) hub from a config entry."""
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


def _async_keep_polling() -> None:
    """Keep the coordinator polling; the presence signal drives the updates."""


async def async_unload_entry(hass: HomeAssistant, entry: UbusConfigEntry) -> None:
    """Unload a config entry.

    The platforms are unloaded first, so the entry's trackers are gone
    before its coordinator is shut down. The coordinator's presence data
    lives on the coordinator, which dies with the entry.
    """
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
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    hub_candidates = [e for e in entries if e.disabled_by is None]
    if not hub_candidates:
        return
    hubs = [e for e in hub_candidates if not e.data]
    hub = min(hubs or hub_candidates, key=lambda e: e.entry_id)
    _async_convert_own_data(hass, hub)
    for other in sorted((e for e in entries if e is not hub), key=lambda e: e.entry_id):
        await _async_migrate_other(hass, hub, other)


async def _async_migrate_other(
    hass: HomeAssistant,
    hub: UbusConfigEntry,
    entry: ConfigEntry,
) -> None:
    """Re-parent a legacy entry into subentries of the hub and remove it.

    The entry is unloaded before its trackers move; a failed unload leaves
    it in place with a repair issue, so its routers keep polling on their
    own entry. A host collision only skips the colliding router; the
    remaining routers are still transferred. Any other failure raises a
    repair issue and leaves the entry in place; the hub setup is never
    blocked by one un-migratable entry.
    """
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    # An entry set up before the migration converted its own data into a
    # subentry, so the host lives in the subentry title then.
    host = entry.data.get(CONF_HOST)
    if host is None:
        host = (
            next(iter(entry.subentries.values())).title
            if entry.subentries
            else entry.entry_id
        )
    try:
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
                    is_fixable=False,
                    issue_domain=DOMAIN,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="migration_failed",
                    translation_placeholders={"host": host},
                )
                return
            _async_reparent(hass, hub, entry, device_registry, entity_registry)
            collision_hosts: list[str] = []
            for subentry in entry.subentries.values():
                try:
                    hass.config_entries.async_add_subentry(
                        hub,
                        ConfigSubentry(
                            data=MappingProxyType(dict(subentry.data)),
                            subentry_type=SUBENTRY_TYPE_ROUTER,
                            title=subentry.title,
                            unique_id=subentry.unique_id,
                        ),
                    )
                except AbortFlow:
                    # A host collision: the hub keeps its copy of this
                    # router, and the remaining routers are still
                    # transferred below.
                    collision_hosts.append(subentry.title)
            if entry.data:
                data = dict(entry.data)
                try:
                    hass.config_entries.async_add_subentry(
                        hub,
                        ConfigSubentry(
                            data=MappingProxyType(data),
                            subentry_type=SUBENTRY_TYPE_ROUTER,
                            title=data[CONF_HOST],
                            unique_id=data[CONF_HOST],
                        ),
                    )
                except AbortFlow:
                    collision_hosts.append(data[CONF_HOST])
            if entry.disabled_by is not None:
                # Subentries cannot be disabled; deleting the subentry
                # reproduces the old "off" behavior.
                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    f"migration_disabled_entry_{entry.entry_id}",
                    is_fixable=False,
                    issue_domain=DOMAIN,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="migration_disabled_entry",
                    translation_placeholders={"host": host},
                )
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
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.ERROR,
                translation_key="migration_host_collision",
                translation_placeholders={"host": ", ".join(collision_hosts)},
            )
    except Exception:
        _LOGGER.exception(
            "Failed to migrate ubus entry %s to the hub %s",
            entry.entry_id,
            hub.entry_id,
        )
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"migration_failed_{entry.entry_id}",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.ERROR,
            translation_key="migration_failed",
            translation_placeholders={"host": host},
        )


@callback
def _async_reparent(
    hass: HomeAssistant,
    hub: UbusConfigEntry,
    entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Re-parent this entry's trackers and devices to the hub.

    A tracker is re-homed before its device: moving a device to another
    entry deletes the old entry's registry entries linked to it.
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
        mac = registry_entry.unique_id
        entity_registry.async_update_entity(
            registry_entry.entity_id, config_entry_id=hub.entry_id
        )
        device = device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, mac), entry.entry_id
        )
        if device is None:
            continue
        target_device = device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, mac), hub.entry_id
        )
        if target_device is not None:
            # Merge the duplicate device into the hub's device, including the
            # disabled entities only the duplicate holds.
            for device_entry in er.async_entries_for_device(
                entity_registry, device.id, include_disabled_entities=True
            ):
                entity_registry.async_update_entity(
                    device_entry.entity_id, device_id=target_device.id
                )
            device_registry.async_remove_device(device.id)
        else:
            device_registry.async_update_device(
                device.id, new_config_entry_id=hub.entry_id
            )
