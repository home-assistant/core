"""The OpenWrt (ubus) integration."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from collections.abc import Mapping
from datetime import timedelta
import logging
from types import MappingProxyType
from typing import Any

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigSubentry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import AnyDeviceEntry

from .const import DOMAIN, SUBENTRY_TYPE_ROUTER
from .coordinator import UbusConfigEntry, UbusDataUpdateCoordinator, UbusSharedState

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.DEVICE_TRACKER]


def _consider_home_from_options(options: Mapping[str, Any]) -> timedelta:
    """Return the configured keep-home window, defaulting to the standard one."""
    seconds = options.get(CONF_CONSIDER_HOME)
    if seconds is None:
        return DEFAULT_CONSIDER_HOME
    return timedelta(seconds=seconds)


def _subentry_signature(entry: ConfigEntry) -> tuple:
    """Return a signature of the entry's subentries, as the coordinators use them."""
    return tuple(
        (
            subentry_id,
            tuple(sorted(subentry.data.items())),
            subentry.title,
            subentry.unique_id,
        )
        for subentry_id, subentry in sorted(entry.subentries.items())
    )


async def _async_entry_updated(hass: HomeAssistant, entry: UbusConfigEntry) -> None:
    """React to a change of the entry.

    Core does not reload an entry when its subentries are added, removed or
    changed, so any subentry change requires an explicit reload to rebuild
    the coordinator set, which also picks up changed router data. An option
    change is applied in place, as a reload would unload every coordinator,
    releasing the stamps, and every tracker would flap unavailable until the
    first refresh completes.
    """
    shared: UbusSharedState = hass.data[DOMAIN]
    if _subentry_signature(entry) != shared.subentry_signatures.get(entry.entry_id):
        shared.reloading_entries.add(entry.entry_id)
        hass.config_entries.async_schedule_reload(entry.entry_id)
        return
    consider_home = _consider_home_from_options(entry.options)
    if consider_home != shared.consider_home:
        shared.consider_home = consider_home
        shared.async_notify(hass)


async def async_setup_entry(hass: HomeAssistant, entry: UbusConfigEntry) -> None:
    """Set up the OpenWrt (ubus) hub from a config entry."""
    shared: UbusSharedState = hass.data.setdefault(DOMAIN, UbusSharedState())
    shared.consider_home = _consider_home_from_options(entry.options)

    # Migrate one-router-per-entry installs before the coordinators are
    # created, so a single setup covers every router of the install.
    await _async_migrate(hass, entry)

    coordinators: dict[str, UbusDataUpdateCoordinator] = {}
    for subentry in entry.subentries.values():
        coordinator = UbusDataUpdateCoordinator(hass, entry, subentry)
        coordinators[subentry.subentry_id] = coordinator
        # A coordinator only polls while it has a listener; the entity
        # updates are driven by the shared presence signal, not by it.
        entry.async_on_unload(coordinator.async_add_listener(_async_keep_polling))
    # A subentry whose first refresh fails does not fail entry setup: it is
    # marked unhealthy and polling continues until it recovers.
    for coordinator in coordinators.values():
        await coordinator.async_refresh()
    entry.runtime_data = coordinators
    shared.subentry_signatures[entry.entry_id] = _subentry_signature(entry)
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


@callback
def _async_keep_polling() -> None:
    """Keep the coordinator polling; the presence signal drives the updates."""


async def async_unload_entry(hass: HomeAssistant, entry: UbusConfigEntry) -> None:
    """Unload a config entry."""
    # The platforms are unloaded first, so the entry's trackers are gone
    # before its client reports are released and the remaining trackers
    # are signalled.
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    shared: UbusSharedState = hass.data[DOMAIN]
    # A subentry change reloads the entry to rebuild the coordinators; the
    # subentries which survive keep their stamps, as their routers keep
    # reporting. Any other unload ends the entry's reporting for good.
    reloading = entry.entry_id in shared.reloading_entries
    shared.reloading_entries.discard(entry.entry_id)
    surviving = set(entry.subentries) if reloading else set()
    for subentry_id, coordinator in entry.runtime_data.items():
        if subentry_id not in surviving:
            coordinator.async_unload()
    shared.subentry_signatures.pop(entry.entry_id, None)
    # The entry is only unregistered after the unload, so the registry still
    # counts it: the state is dropped when this entry is the last one, unless
    # it is reloading, as the surviving coordinators' stamps must not be lost.
    if not reloading and len(hass.config_entries.async_entries(DOMAIN)) == 1:
        hass.data.pop(DOMAIN, None)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: UbusConfigEntry, device_entry: AnyDeviceEntry
) -> bool:
    """Allow removing a client device which is not currently connected."""
    if not isinstance(device_entry, dr.DeviceEntry):
        # This integration does not create child devices.
        return False
    if config_entry.state is not ConfigEntryState.LOADED:
        return True
    shared: UbusSharedState = hass.data[DOMAIN]
    return all(
        shared.latest_stamp(dr.format_mac(connection)) is None
        for connection_type, connection in device_entry.connections
        if connection_type == dr.CONNECTION_NETWORK_MAC
    )


def _async_convert_own_data(hass: HomeAssistant, entry: UbusConfigEntry) -> None:
    """Move this entry's own router data into a subentry, making it a pure hub.

    No-op when the entry already holds no router data.
    """
    if not entry.data:
        return
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
    hass.config_entries.async_update_entry(entry, data={})


async def _async_migrate(hass: HomeAssistant, entry: UbusConfigEntry) -> None:
    """Migrate a one-router-per-entry install to the hub-and-subentry model.

    The entry with the lowest id among the entries which are not disabled
    becomes the hub and runs the migration, so it happens exactly once
    across the install. It converts its own router data into a subentry and
    re-parents every other entry (including disabled ones) into a subentry,
    then removes those entries.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    hub_candidates = [e for e in entries if e.disabled_by is None]
    if not hub_candidates:
        return
    if min(hub_candidates, key=lambda e: e.entry_id) is not entry:
        return
    _async_convert_own_data(hass, entry)
    for other in sorted(
        (e for e in entries if e is not entry), key=lambda e: e.entry_id
    ):
        await _async_migrate_other(hass, entry, other)
    shared: UbusSharedState = hass.data[DOMAIN]
    shared.async_notify(hass)


async def _async_migrate_other(
    hass: HomeAssistant,
    hub: UbusConfigEntry,
    entry: ConfigEntry,
) -> None:
    """Re-parent a legacy entry into subentries of the hub and remove it.

    A failure raises a repair issue and leaves the entry in place; the hub
    setup is never blocked by one un-migratable entry.
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
        # Hold the entry's setup lock so it is never removed mid-setup.
        async with entry.setup_lock:
            _async_reparent(hass, hub, entry, device_registry, entity_registry)
            for subentry in entry.subentries.values():
                hass.config_entries.async_add_subentry(
                    hub,
                    ConfigSubentry(
                        data=MappingProxyType(dict(subentry.data)),
                        subentry_type=SUBENTRY_TYPE_ROUTER,
                        title=subentry.title,
                        unique_id=subentry.unique_id,
                    ),
                )
            if entry.data:
                data = dict(entry.data)
                hass.config_entries.async_add_subentry(
                    hub,
                    ConfigSubentry(
                        data=MappingProxyType(data),
                        subentry_type=SUBENTRY_TYPE_ROUTER,
                        title=data[CONF_HOST],
                        unique_id=data[CONF_HOST],
                    ),
                )
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
        # The removal waits out any setup this entry still has in progress.
        await hass.config_entries.async_remove(entry.entry_id)
    except AbortFlow:
        # A host collision: the hub keeps the colliding subentry and this
        # entry is still removed, so a repair issue tells the user what
        # happened.
        _LOGGER.warning(
            "Host %s already exists on the hub; removing the duplicate ubus entry",
            host,
        )
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"migration_host_collision_{entry.entry_id}",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.ERROR,
            translation_key="migration_host_collision",
            translation_placeholders={"host": host},
        )
        await hass.config_entries.async_remove(entry.entry_id)
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
