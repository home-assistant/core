"""Support for OpenWrt (ubus) routers as a device tracker."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

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
    for entry in hass.config_entries.async_entries(DOMAIN):
        if device := device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, mac), entry.entry_id
        ):
            device_registry.async_update_device(
                device.id, new_config_entry_id=config_entry_id
            )


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
            device_registry.async_update_device(
                device.id, new_config_entry_id=config_entry.entry_id
            )

    @callback
    def _async_update_devices() -> None:
        new_macs = [mac for mac in coordinator.data if mac not in tracked]
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
                    # A loaded owner keeps its claim, so only take over a
                    # tracker whose owner has no live claim on the MAC (e.g. it
                    # is offline and its platform never loaded, as after a
                    # restart).
                    if shared.owners.get(mac) is not None:
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
    def _async_rename_devices() -> None:
        # Rename here, as trackers are disabled by default and get no updates.
        for mac, seen_by in shared.reports.items():
            if (source := shared.source(mac)) is None:
                continue
            if (
                (hostname := seen_by[source].hostname)
                and (
                    device_entry := device_registry.async_get_device_by_connection(
                        (dr.CONNECTION_NETWORK_MAC, mac), config_entry.entry_id
                    )
                )
                and device_entry.name != hostname
            ):
                device_registry.async_update_device(device_entry.id, name=hostname)

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
        _async_update_devices()

    # Recreate the trackers this entry owns so it keeps reporting clients
    # connected to another router.
    for registry_entry in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):
        if (
            registry_entry.domain != DEVICE_TRACKER_DOMAIN
            or registry_entry.platform != DOMAIN
            or registry_entry.unique_id is None
            or registry_entry.unique_id in tracked
        ):
            continue
        mac = registry_entry.unique_id
        tracked.add(mac)
        shared.owners.setdefault(mac, config_entry.entry_id)
        async_add_entities([UbusScannerEntity(coordinator, mac)])

    config_entry.async_on_unload(coordinator.async_add_listener(_async_update_devices))
    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_CLIENTS_UPDATED, _async_rename_devices)
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
    _async_rename_devices()


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
        return self._mac in self.hass.data[DOMAIN].reports

    @property
    @override
    def hostname(self) -> str | None:
        """Return the hostname of the device."""
        shared: UbusSharedState = self.hass.data[DOMAIN]
        if (source := shared.source(self._mac)) is None:
            return None
        return shared.reports[self._mac][source].hostname

    @property
    @override
    def available(self) -> bool:
        """Return whether the device state is reported by any ubus router."""
        shared: UbusSharedState = self.hass.data[DOMAIN]
        if self._mac in shared.reports:
            return True
        # A router which can't be read may still be connected to the device.
        return all(
            shared.health.get(entry.data[CONF_HOST], True)
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.state
            in (
                ConfigEntryState.LOADED,
                ConfigEntryState.SETUP_IN_PROGRESS,
                ConfigEntryState.SETUP_RETRY,
            )
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the source attribute identifying the reporting router."""
        shared: UbusSharedState = self.hass.data[DOMAIN]
        if (source := shared.source(self._mac)) is None:
            return None
        return {"source": source}

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
