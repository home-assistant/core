"""Device tracker platform for Meraki Dashboard."""

from __future__ import annotations

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NETWORK_ID
from .coordinator import (
    MerakiDashboardClient,
    MerakiDashboardConfigEntry,
    MerakiDashboardDataUpdateCoordinator,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MerakiDashboardConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Meraki Dashboard device tracker entities."""
    coordinator = config_entry.runtime_data
    tracked_clients: set[str] = set()

    @callback
    def async_add_new_entities() -> None:
        latest_clients = set(coordinator.data.clients)
        entities = [
            MerakiDashboardDeviceTrackerEntity(
                coordinator=coordinator,
                network_id=config_entry.data[CONF_NETWORK_ID],
                mac_address=mac_address,
            )
            for mac_address in latest_clients - tracked_clients
        ]
        tracked_clients.update(latest_clients)
        if entities:
            async_add_entities(entities)

    async_add_new_entities()
    config_entry.async_on_unload(coordinator.async_add_listener(async_add_new_entities))


class MerakiDashboardDeviceTrackerEntity(
    CoordinatorEntity[MerakiDashboardDataUpdateCoordinator], ScannerEntity
):
    """Representation of a Meraki Dashboard network client."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MerakiDashboardDataUpdateCoordinator,
        network_id: str,
        mac_address: str,
    ) -> None:
        """Initialize the device tracker entity."""
        super().__init__(coordinator)
        self._mac_address = mac_address
        self._attr_unique_id = f"{network_id}_{mac_address}"
        self._attr_mac_address = mac_address

    @property
    def _client(self) -> MerakiDashboardClient | None:
        """Return the current client data."""
        return self.coordinator.data.clients.get(self._mac_address)

    @property
    def name(self) -> str:
        """Return the entity name."""
        if (client := self._client) is None:
            return self._mac_address
        return (
            client.description or client.dhcp_hostname or client.mdns_name or client.mac
        )

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.ROUTER

    @property
    def is_connected(self) -> bool:
        """Return whether this client is connected."""
        return self._client is not None and self._client.status == "Online"

    @property
    def ip_address(self) -> str | None:
        """Return the IP address."""
        if (client := self._client) is None:
            return None
        return client.ip_address

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Enable entity by default."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, str | int | None]:
        """Return extra state attributes."""
        if (client := self._client) is None:
            return {}

        connection_summary = None
        if (
            client.recent_device_name
            and client.recent_device_serial
            and client.recent_device_connection
        ):
            connection_summary = (
                f"{client.recent_device_connection} via "
                f"{client.recent_device_name} ({client.recent_device_serial})"
            )

        return {
            "manufacturer": client.manufacturer,
            "ip6": client.ip6_address,
            "connection_summary": connection_summary,
            "connection_type": client.recent_device_connection,
            "connected_via_device_name": client.recent_device_name,
            "connected_via_device_serial": client.recent_device_serial,
            "connected_via_ssid": client.ssid,
            "connected_via_vlan": client.vlan,
            "connected_via_named_vlan": client.named_vlan,
            "connected_via_switchport": client.switchport,
            "recent_device_name": client.recent_device_name,
            "recent_device_serial": client.recent_device_serial,
            "recent_device_connection": client.recent_device_connection,
            "first_seen": client.first_seen,
            "last_seen": client.last_seen,
            "ssid": client.ssid,
            "vlan": client.vlan,
        }
