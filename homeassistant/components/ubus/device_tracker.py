"""Support for OpenWrt (ubus) routers as a device tracker."""

from functools import partial
from typing import TYPE_CHECKING, Any, override

import probatio

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    Event,
    HomeAssistant,
    callback,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_DHCP_SOFTWARE,
    DEFAULT_DHCP_SOFTWARE,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DHCP_SOFTWARES,
    DOMAIN,
    SIGNAL_CLIENTS_UPDATED,
)
from .coordinator import UbusConfigEntry, UbusDataUpdateCoordinator

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): cv.string,
        probatio.Required(CONF_USERNAME): cv.string,
        probatio.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        probatio.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        probatio.Optional(
            CONF_DHCP_SOFTWARE, default=DEFAULT_DHCP_SOFTWARE
        ): probatio.In(DHCP_SOFTWARES),
    }
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Import the legacy YAML device tracker into a config entry."""
    import_data = {
        CONF_HOST: config[CONF_HOST],
        CONF_USERNAME: config[CONF_USERNAME],
        CONF_PASSWORD: config[CONF_PASSWORD],
        CONF_SSL: config[CONF_SSL],
        CONF_VERIFY_SSL: config[CONF_VERIFY_SSL],
        CONF_DHCP_SOFTWARE: config[CONF_DHCP_SOFTWARE],
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=import_data
    )

    if result["type"] is FlowResultType.ABORT and result["reason"] in (
        "cannot_connect",
        "invalid_auth",
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"yaml_import_{result['reason']}",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.ERROR,
            translation_key=f"yaml_import_{result['reason']}",
            translation_placeholders={"host": config[CONF_HOST]},
        )
        return False

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.5.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "OpenWrt (ubus)",
        },
    )
    return True


@callback
def _async_migrate_unique_ids(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry_id: str,
) -> None:
    """Normalize pre-existing tracker unique ids to lowercase MACs.

    Trackers created before MACs were normalized keep the router's raw
    case; re-pointing the unique id reuses the entity, with its entity
    id and customizations, instead of creating a duplicate. Duplicate
    trackers' person references and devices are preserved: references
    follow the surviving tracker, and duplicate devices are merged into
    the survivor's device, with their references following it.
    """
    by_mac: dict[str, list[er.RegistryEntry]] = {}
    for registry_entry in er.async_entries_for_config_entry(
        entity_registry, config_entry_id
    ):
        if (
            registry_entry.domain == DEVICE_TRACKER_DOMAIN
            and registry_entry.platform == DOMAIN
            and registry_entry.unique_id is not None
        ):
            by_mac.setdefault(registry_entry.unique_id.lower(), []).append(
                registry_entry
            )
    # A tracker disabled only by its config entry or device is in a
    # derived state which clears when those are re-enabled, so it still
    # counts as an established tracker.
    derived_disabled = (
        None,
        er.RegistryEntryDisabler.CONFIG_ENTRY,
        er.RegistryEntryDisabler.DEVICE,
    )
    for entries in by_mac.values():
        if len(entries) == 1 and entries[0].unique_id == entries[0].unique_id.lower():
            continue
        # An enabled tracker is the established one over a disabled
        # duplicate; between equally established trackers the oldest wins.
        candidates = [
            entry for entry in entries if entry.disabled_by in derived_disabled
        ] or entries
        survivor = min(candidates, key=lambda entry: entry.created_at)
        for entry in entries:
            if entry is not survivor:
                # The duplicate's tracker and, with it, its device are
                # gone now; the references to them follow the survivor.
                hass.async_create_task(
                    _async_repoint_tracker_references(
                        hass, entry.entity_id, survivor.entity_id
                    )
                )
                if (
                    entry.device_id is not None
                    and survivor.device_id is not None
                    and entry.device_id != survivor.device_id
                ):
                    hass.async_create_task(
                        _async_repoint_device_references(
                            hass, entry.device_id, survivor.device_id
                        )
                    )
                entity_registry.async_remove(entry.entity_id)
                _async_merge_device(device_registry, entity_registry, entry, survivor)
        if survivor.unique_id != survivor.unique_id.lower():
            # Another entry may own the normalized unique id already,
            # such as a failed migration or a newer-schema entry which
            # the consolidation leaves in place; the registry would
            # raise on the rename and abort the whole platform.
            if (
                entity_registry.async_get_entity_id(
                    DEVICE_TRACKER_DOMAIN, DOMAIN, survivor.unique_id.lower()
                )
                is None
            ):
                entity_registry.async_update_entity(
                    survivor.entity_id, new_unique_id=survivor.unique_id.lower()
                )


@callback
def _async_merge_device(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entry: er.RegistryEntry,
    survivor: er.RegistryEntry,
) -> None:
    """Merge a duplicate tracker's device into the survivor's device.

    Left behind, the duplicate's device is where a later re-parent
    attaches the survivor, and deleting the survivor's device then
    drops the survivor's own device, with its area, name and
    automation references.
    """
    dup_device = device_registry.async_get(entry.device_id) if entry.device_id else None
    survivor_device = (
        device_registry.async_get(survivor.device_id) if survivor.device_id else None
    )
    if dup_device is None or dup_device is survivor_device:
        return
    if survivor_device is None:
        # The survivor has no device; keep the duplicate's, moved to the
        # survivor's config entry.
        if survivor.config_entry_id is None:
            return
        device_registry.async_update_device(
            dup_device.id, new_config_entry_id=survivor.config_entry_id
        )
        entity_registry.async_update_entity(survivor.entity_id, device_id=dup_device.id)
        return
    # The device removal below deletes the registry entries the entry still
    # holds on it, so the disabled entities must be moved along too.
    for device_entry in er.async_entries_for_device(
        entity_registry, dup_device.id, include_disabled_entities=True
    ):
        entity_registry.async_update_entity(
            device_entry.entity_id, device_id=survivor_device.id
        )
    device_registry.async_remove_device(dup_device.id)


async def _async_repoint_tracker_references(
    hass: HomeAssistant,
    removed_entity_id: str,
    survivor_entity_id: str,
) -> None:
    """Re-point references at the surviving tracker after a duplicate is removed.

    Entry data holding device tracker entity ids, such as person
    configurations, is left pointing at the removed tracker, so the
    references move to the tracker that keeps the client.
    """
    for config_entry in hass.config_entries.async_entries():
        device_trackers = config_entry.data.get("device_trackers")
        if (
            not isinstance(device_trackers, list)
            or removed_entity_id not in device_trackers
        ):
            continue
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                **config_entry.data,
                "device_trackers": [
                    survivor_entity_id if entity_id == removed_entity_id else entity_id
                    for entity_id in device_trackers
                ],
            },
        )


async def _async_repoint_device_references(
    hass: HomeAssistant,
    removed_device_id: str,
    survivor_device_id: str,
) -> None:
    """Re-point device references at the surviving device after a merge.

    Entry data holding device ids, such as device automations, is left
    pointing at the removed device, which would fail validation, so the
    references move to the device that survives the merge.
    """
    for config_entry in hass.config_entries.async_entries():
        triggers = config_entry.data.get("trigger")
        if not isinstance(triggers, list):
            continue
        new_triggers: list[dict[str, Any]] = []
        changed = False
        for trigger in triggers:
            if (
                isinstance(trigger, dict)
                and trigger.get("device_id") == removed_device_id
            ):
                trigger = {**trigger, "device_id": survivor_device_id}
                changed = True
            new_triggers.append(trigger)
        if changed:
            hass.config_entries.async_update_entry(
                config_entry, data={**config_entry.data, "trigger": new_triggers}
            )


@callback
def _async_rename_devices(
    coordinator: UbusDataUpdateCoordinator,
    device_registry: dr.DeviceRegistry,
    config_entry_id: str,
) -> None:
    """Rename devices when a client hostname is seen.

    Rename here, as trackers are disabled by default and get no updates.
    """
    for mac in coordinator.data_or_none or {}:
        if (stamp := coordinator.latest_stamp(mac)) is None:
            continue
        if (
            (hostname := stamp[1].hostname or coordinator.known_hostname(mac))
            and (
                device_entry := device_registry.async_get_device_by_connection(
                    (dr.CONNECTION_NETWORK_MAC, mac), config_entry_id
                )
            )
            and device_entry.name != hostname
        ):
            device_registry.async_update_device(device_entry.id, name=hostname)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the device tracker for the ubus hub."""
    tracked: set[str] = set()

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    coordinator: UbusDataUpdateCoordinator = config_entry.runtime_data

    _async_migrate_unique_ids(
        hass, device_registry, entity_registry, config_entry.entry_id
    )

    @callback
    def _async_update_devices() -> None:
        # Registry removal events of this entry's own devices and entities
        # still fire while it unloads, which would re-discover its own
        # clients: stay out of the way.
        if config_entry.state is ConfigEntryState.UNLOAD_IN_PROGRESS:
            return
        seen: set[str] = set()
        # A failed poll sees nothing new.
        for clients in coordinator.latest_views.values():
            seen.update(clients)
        # Trackers this entry holds in the registry must stay live even
        # when no router sees their client, as a restored registry entry
        # cannot report the absence on its own.
        owned = {
            registry_entry.unique_id
            for registry_entry in er.async_entries_for_config_entry(
                entity_registry, config_entry.entry_id
            )
            if registry_entry.domain == DEVICE_TRACKER_DOMAIN
            and registry_entry.platform == DOMAIN
            and registry_entry.unique_id is not None
        }
        new_macs = [mac for mac in seen | owned if mac not in tracked]
        tracked.update(new_macs)
        if new_macs:
            async_add_entities(
                UbusScannerEntity(hass, config_entry, mac) for mac in new_macs
            )

    @callback
    def _async_device_removed(
        event: Event[dr.EventDeviceRegistryUpdatedData],
    ) -> None:
        """Track a client again if it reconnects after its device was removed."""
        if TYPE_CHECKING:
            assert event.data["action"] == "remove"
        connections = set(event.data["device"]["connections"])
        removed = {
            mac
            for mac in tracked
            if (dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac)) in connections
        }
        tracked.difference_update(removed)

    @callback
    def _is_own_device_removed(event_data: dr.EventDeviceRegistryUpdatedData) -> bool:
        return (
            event_data["action"] == "remove"
            and event_data["device"]["config_entry_id"] == config_entry.entry_id
        )

    @callback
    def _is_entity_removed(event_data: er.EventEntityRegistryUpdatedData) -> bool:
        return event_data["action"] == "remove"

    @callback
    def _async_entity_removed(
        event: Event[er.EventEntityRegistryUpdatedData],
    ) -> None:
        """Track a client again when its tracker registry entry is removed."""
        if TYPE_CHECKING:
            assert event.data["action"] == "remove"
        entity_id = event.data["entity_id"]
        for mac in list(tracked):
            deleted = entity_registry.deleted_entities.get(
                (DEVICE_TRACKER_DOMAIN, DOMAIN, mac)
            )
            if deleted is not None and deleted.entity_id == entity_id:
                tracked.discard(mac)
                break
        else:
            return
        # Defer rediscovery until the old entity's removal has released its
        # entity ID; otherwise the recreated tracker gets a suffixed one.
        hass.loop.call_soon(_async_update_devices)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_CLIENTS_UPDATED,
            _async_update_devices,
        )
    )
    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_CLIENTS_UPDATED,
            partial(
                _async_rename_devices,
                coordinator,
                device_registry,
                config_entry.entry_id,
            ),
        )
    )
    config_entry.async_on_unload(
        hass.bus.async_listen(
            dr.EVENT_DEVICE_REGISTRY_UPDATED,
            _async_device_removed,
            event_filter=_is_own_device_removed,
        )
    )
    config_entry.async_on_unload(
        hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            _async_entity_removed,
            event_filter=_is_entity_removed,
        )
    )
    _async_update_devices()
    _async_rename_devices(coordinator, device_registry, config_entry.entry_id)


class UbusScannerEntity(ScannerEntity):
    """Representation of a device connected to an OpenWrt router."""

    # The state is driven by the hub's coordinator, not by per-entity
    # polling; manual refreshes go through async_update.
    _attr_should_poll = False

    def __init__(
        self, hass: HomeAssistant, config_entry: UbusConfigEntry, mac: str
    ) -> None:
        """Initialize the tracked device."""
        super().__init__()
        self._config_entry = config_entry
        self._mac = mac
        connection = (dr.CONNECTION_NETWORK_MAC, mac)
        coordinator: UbusDataUpdateCoordinator = config_entry.runtime_data
        hostname: str | None = None
        if (stamp := coordinator.latest_stamp(mac)) is not None:
            hostname = stamp[1].hostname
        if not hostname:
            # The newest stamp may have no lease; fall back to the hostname
            # the client was known by before.
            hostname = coordinator.known_hostname(mac)
        if hostname:
            self._attr_device_info = dr.DeviceInfo(
                connections={connection}, name=hostname
            )
        elif dr.async_get(hass).async_get_device_by_connection(
            connection, config_entry.entry_id
        ):
            # Without a hostname, keep the name of an existing device.
            self._attr_device_info = dr.DeviceInfo(connections={connection})
        else:
            self._attr_device_info = dr.DeviceInfo(connections={connection}, name=mac)

    @property
    @override
    def mac_address(self) -> str:
        """Return the MAC address of the device."""
        return self._mac

    @property
    @override
    def is_connected(self) -> bool:
        """Return whether the device is connected to any ubus router."""
        coordinator: UbusDataUpdateCoordinator = self._config_entry.runtime_data
        return coordinator.latest_stamp(self._mac) is not None

    @property
    @override
    def hostname(self) -> str | None:
        """Return the hostname of the device."""
        coordinator: UbusDataUpdateCoordinator = self._config_entry.runtime_data
        if (stamp := coordinator.latest_stamp(self._mac)) is None:
            return None
        # The latest router may have no lease for the client; fall back to
        # the hostname the client was known by before.
        return stamp[1].hostname or coordinator.known_hostname(self._mac)

    @property
    @override
    def available(self) -> bool:
        """Return whether the device's state is grounded on a reachable router."""
        coordinator: UbusDataUpdateCoordinator = self._config_entry.runtime_data
        return super().available and (
            coordinator.has_reportable_stamp(self._mac)
            or coordinator.known_away(self._mac)
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the source attribute identifying the reporting router."""
        coordinator: UbusDataUpdateCoordinator = self._config_entry.runtime_data
        if (stamp := coordinator.latest_stamp(self._mac)) is None:
            return None
        subentry = self._config_entry.subentries.get(stamp[0])
        if subentry is None:
            # The reporter's subentry may be removed before the next tick
            # drops its stamp.
            return None
        return {"source": subentry.data[CONF_HOST]}

    async def async_update(self) -> None:
        """Refresh the router client lists on request."""
        await self._config_entry.runtime_data.async_request_refresh()

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to client list updates from the routers."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_CLIENTS_UPDATED, self._async_clients_updated
            )
        )

    @callback
    def _async_clients_updated(self) -> None:
        """Write the state when the client list changes."""
        self.async_write_ha_state()
