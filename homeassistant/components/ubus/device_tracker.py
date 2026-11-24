"""Support for OpenWrt (ubus) routers as a device tracker."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from functools import partial
from typing import TYPE_CHECKING, override

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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DHCP_SOFTWARE,
    DEFAULT_DHCP_SOFTWARE,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DHCP_SOFTWARES,
    DOMAIN,
    SIGNAL_CLIENTS_UPDATED,
)
from .coordinator import UbusConfigEntry, UbusDataUpdateCoordinator, UbusSharedState

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
def _async_rehome_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry_id: str,
    mac: str,
) -> None:
    """Move a device left behind for this client, avoiding a duplicate."""
    connection = (dr.CONNECTION_NETWORK_MAC, mac)
    if device_registry.async_get_device_by_connection(connection, config_entry_id):
        return
    for entry in hass.config_entries.async_entries(DOMAIN):
        if device := device_registry.async_get_device_by_connection(
            connection, entry.entry_id
        ):
            device_registry.async_update_device(
                device.id, new_config_entry_id=config_entry_id
            )
            return


@callback
def _async_release_removed_claim(
    entity_registry: er.EntityRegistry,
    entity_id: str,
    tracked: set[str],
    shared: UbusSharedState,
) -> None:
    """Release the claim on the MAC whose tracker was removed from the registry."""
    if not entity_id.startswith(f"{DEVICE_TRACKER_DOMAIN}."):
        return
    for mac in list(tracked):
        deleted = entity_registry.deleted_entities.get(
            (DEVICE_TRACKER_DOMAIN, DOMAIN, mac)
        )
        if deleted is not None and deleted.entity_id == entity_id:
            # A stale claim would block another entry from recreating the
            # tracker when the client reconnects to a different router.
            tracked.discard(mac)
            shared.owners.pop(mac, None)


def _can_take_over_tracker(
    hass: HomeAssistant,
    shared: UbusSharedState,
    mac: str,
    owner_entry_id: str | None,
) -> bool:
    """Check whether a tracker can be taken over from its owner.

    A loaded owner keeps its claim, so only a tracker whose owner has no
    live claim on the MAC and isn't loading (e.g. it is offline and its
    platform never loaded, as after a restart) can be taken over.
    """
    if shared.owners.get(mac) is not None:
        return False
    if owner_entry_id is None:
        return True
    owner_entry = hass.config_entries.async_get_entry(owner_entry_id)
    return owner_entry is None or owner_entry.state not in (
        ConfigEntryState.LOADED,
        ConfigEntryState.SETUP_IN_PROGRESS,
    )


@callback
def _async_rename_devices(
    shared: UbusSharedState,
    device_registry: dr.DeviceRegistry,
    config_entry_id: str,
) -> None:
    """Rename devices when a client hostname is seen.

    Rename here, as trackers are disabled by default and get no updates.
    """
    for mac in shared.presence:
        if (stamp := shared.latest_stamp(mac)) is None:
            continue
        if (
            (hostname := stamp[1].hostname)
            and (
                device_entry := device_registry.async_get_device_by_connection(
                    (dr.CONNECTION_NETWORK_MAC, mac), config_entry_id
                )
            )
            and device_entry.name != hostname
        ):
            device_registry.async_update_device(device_entry.id, name=hostname)


@callback
def _async_migrate_unique_ids(entity_registry: er.EntityRegistry) -> None:
    """Normalize pre-existing tracker unique ids to lowercase MACs.

    Trackers created before MACs were normalized keep the router's raw
    case; re-pointing the unique id reuses the entity, with its entity
    id and customizations, instead of creating a duplicate.
    """
    by_mac: dict[str, list[er.RegistryEntry]] = {}
    for registry_entry in entity_registry.entities.values():
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
                entity_registry.async_remove(entry.entity_id)
        if survivor.unique_id != survivor.unique_id.lower():
            entity_registry.async_update_entity(
                survivor.entity_id, new_unique_id=survivor.unique_id.lower()
            )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the device tracker for a ubus config entry."""
    coordinator = config_entry.runtime_data
    tracked: set[str] = set()

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    shared: UbusSharedState = hass.data[DOMAIN]

    _async_migrate_unique_ids(entity_registry)

    @callback
    def _async_take_over(mac: str, entity_id: str, previous_owner: str | None) -> None:
        """Re-home a tracker whose previous owner no longer hosts it."""
        entity_registry.async_update_entity(
            entity_id, config_entry_id=config_entry.entry_id
        )
        if previous_owner is None:
            return
        # Move the previous owner's device, so this entry's tracker reuses it
        # instead of creating a duplicate for the same client.
        device = device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, mac), previous_owner
        )
        if device is not None:
            target_device = device_registry.async_get_device_by_connection(
                (dr.CONNECTION_NETWORK_MAC, mac), config_entry.entry_id
            )
            if target_device is not None:
                entity_registry.async_update_entity(
                    entity_id, device_id=target_device.id
                )
            else:
                device_registry.async_update_device(
                    device.id, new_config_entry_id=config_entry.entry_id
                )

    @callback
    def _async_update_devices() -> None:
        # Track every client this router sees, plus every tracker this entry
        # owns, so it keeps reporting clients connected to another router.
        owned = {
            registry_entry.unique_id
            for registry_entry in er.async_entries_for_config_entry(
                entity_registry, config_entry.entry_id
            )
            if registry_entry.domain == DEVICE_TRACKER_DOMAIN
            and registry_entry.platform == DOMAIN
            and registry_entry.unique_id is not None
        }
        # A failed poll sees nothing new, but trackers handed over to this
        # entry must still be recreated while its own polls fail.
        seen: set[str] = (
            set(coordinator.data) if coordinator.last_update_success else set()
        )
        new_macs = [mac for mac in seen | owned if mac not in tracked]
        claimed: list[str] = []
        for mac in new_macs:
            # One tracker per MAC: an entry only creates a tracker it owns, so
            # another entry's tracker for the same MAC is left alone, unless
            # that entry no longer hosts it.
            entity_id = entity_registry.async_get_entity_id(
                DEVICE_TRACKER_DOMAIN, DOMAIN, mac
            )
            if entity_id is not None:
                registry_entry = entity_registry.async_get(entity_id)
                if (
                    registry_entry is not None
                    and registry_entry.config_entry_id != config_entry.entry_id
                ):
                    if not _can_take_over_tracker(
                        hass, shared, mac, registry_entry.config_entry_id
                    ):
                        continue
                    _async_take_over(mac, entity_id, registry_entry.config_entry_id)
            # The claim is made before adding the entity so two entries which
            # see the same client at setup time don't both create it.
            if (
                shared.owners.setdefault(mac, config_entry.entry_id)
                != config_entry.entry_id
            ):
                continue
            if entity_id is None:
                _async_rehome_devices(hass, device_registry, config_entry.entry_id, mac)
            tracked.add(mac)
            claimed.append(mac)
        if claimed:
            async_add_entities(UbusScannerEntity(coordinator, mac) for mac in claimed)

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
        for mac in removed:
            # Release the claim so another entry can create the tracker if
            # the client reconnects to a different router.
            shared.owners.pop(mac, None)

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
        """Track a client again when its registry entry is removed."""
        if TYPE_CHECKING:
            assert event.data["action"] == "remove"
        _async_release_removed_claim(
            entity_registry, event.data["entity_id"], tracked, shared
        )
        # Defer rediscovery until the old entity's removal has released its
        # entity ID; otherwise the recreated tracker gets a suffixed one.
        hass.loop.call_soon(_async_update_devices)

    config_entry.async_on_unload(coordinator.async_add_listener(_async_update_devices))
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
                shared,
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
    _async_rename_devices(shared, device_registry, config_entry.entry_id)


class UbusScannerEntity(CoordinatorEntity[UbusDataUpdateCoordinator], ScannerEntity):
    """Representation of a device connected to an OpenWrt router."""

    def __init__(self, coordinator: UbusDataUpdateCoordinator, mac: str) -> None:
        """Initialize the tracked device."""
        super().__init__(coordinator)
        self._mac = mac
        connection = (dr.CONNECTION_NETWORK_MAC, mac)
        if name := coordinator.data.get(mac):
            self._attr_device_info = dr.DeviceInfo(connections={connection}, name=name)
        elif dr.async_get(coordinator.hass).async_get_device_by_connection(
            connection, coordinator.config_entry.entry_id
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
        shared: UbusSharedState = self.hass.data[DOMAIN]
        return shared.latest_stamp(self._mac) is not None

    @property
    @override
    def hostname(self) -> str | None:
        """Return the hostname of the device."""
        shared: UbusSharedState = self.hass.data[DOMAIN]
        if (stamp := shared.latest_stamp(self._mac)) is None:
            return None
        # The latest router may have no lease for the client; fall back to
        # the hostname the client was known by before.
        return stamp[1].hostname or shared.known_hostname(self._mac)

    @property
    @override
    def available(self) -> bool:
        """Return whether any healthy ubus router has seen the device."""
        shared: UbusSharedState = self.hass.data[DOMAIN]
        return shared.has_healthy_stamp(self._mac)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the source attribute identifying the reporting router."""
        shared: UbusSharedState = self.hass.data[DOMAIN]
        if (stamp := shared.latest_stamp(self._mac)) is None:
            return None
        reporter = self.hass.config_entries.async_get_entry(stamp[0])
        if reporter is None:
            return None
        return {"source": reporter.data[CONF_HOST]}

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to client list updates from the other routers."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_CLIENTS_UPDATED, self._async_clients_updated
            )
        )

    @callback
    def _async_clients_updated(self) -> None:
        """Write the state when another router's client list changes."""
        self.async_write_ha_state()
