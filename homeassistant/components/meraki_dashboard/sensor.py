"""Diagnostic sensors for Meraki Dashboard infrastructure devices."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    MerakiDashboardConfigEntry,
    MerakiDashboardDataUpdateCoordinator,
    MerakiDashboardInfrastructureDevice,
)


@dataclass(frozen=True, kw_only=True)
class MerakiDashboardSensorEntityDescription(SensorEntityDescription):
    """Description for Meraki Dashboard diagnostic sensors."""

    value_key: str
    product_types: set[str] | None = None


SENSORS: tuple[MerakiDashboardSensorEntityDescription, ...] = (
    MerakiDashboardSensorEntityDescription(
        key="serial",
        name="Serial",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="serial",
    ),
    MerakiDashboardSensorEntityDescription(
        key="model",
        name="Model",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="model",
    ),
    MerakiDashboardSensorEntityDescription(
        key="mac",
        name="MAC",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="mac",
    ),
    MerakiDashboardSensorEntityDescription(
        key="product_type",
        name="Product type",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="product_type",
    ),
    MerakiDashboardSensorEntityDescription(
        key="status",
        name="Status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="status",
    ),
    MerakiDashboardSensorEntityDescription(
        key="network_id",
        name="Network ID",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="network_id",
    ),
    MerakiDashboardSensorEntityDescription(
        key="public_ip",
        name="Public IP",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="public_ip",
    ),
    MerakiDashboardSensorEntityDescription(
        key="lan_ip",
        name="LAN IP",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="lan_ip",
    ),
    MerakiDashboardSensorEntityDescription(
        key="gateway",
        name="Gateway",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="gateway",
    ),
    MerakiDashboardSensorEntityDescription(
        key="ip_type",
        name="IP type",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="ip_type",
    ),
    MerakiDashboardSensorEntityDescription(
        key="primary_dns",
        name="Primary DNS",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="primary_dns",
    ),
    MerakiDashboardSensorEntityDescription(
        key="secondary_dns",
        name="Secondary DNS",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="secondary_dns",
    ),
    MerakiDashboardSensorEntityDescription(
        key="last_reported_at",
        name="Last reported at",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="last_reported_at",
    ),
    MerakiDashboardSensorEntityDescription(
        key="wireless_clients",
        name="Wireless clients",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="wireless_clients",
        product_types={"wireless"},
    ),
    MerakiDashboardSensorEntityDescription(
        key="ap_enabled_ssids",
        name="Enabled SSIDs",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="ap_enabled_ssids",
        product_types={"wireless"},
    ),
    MerakiDashboardSensorEntityDescription(
        key="ap_channels_in_use",
        name="Channels in use",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="ap_channels_in_use",
        product_types={"wireless"},
    ),
    MerakiDashboardSensorEntityDescription(
        key="ap_bands_in_use",
        name="Bands in use",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="ap_bands_in_use",
        product_types={"wireless"},
    ),
    MerakiDashboardSensorEntityDescription(
        key="ap_channels_2_4ghz",
        name="2.4 GHz channels",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="ap_channels_2_4ghz",
        product_types={"wireless"},
    ),
    MerakiDashboardSensorEntityDescription(
        key="ap_channels_5ghz",
        name="5 GHz channels",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="ap_channels_5ghz",
        product_types={"wireless"},
    ),
    MerakiDashboardSensorEntityDescription(
        key="ap_channels_6ghz",
        name="6 GHz channels",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="ap_channels_6ghz",
        product_types={"wireless"},
    ),
    MerakiDashboardSensorEntityDescription(
        key="ap_channel_utilization_2_4ghz",
        name="2.4 GHz channel utilization",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="ap_channel_utilization_2_4ghz",
        native_unit_of_measurement=PERCENTAGE,
        product_types={"wireless"},
    ),
    MerakiDashboardSensorEntityDescription(
        key="ap_channel_utilization_5ghz",
        name="5 GHz channel utilization",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="ap_channel_utilization_5ghz",
        native_unit_of_measurement=PERCENTAGE,
        product_types={"wireless"},
    ),
    MerakiDashboardSensorEntityDescription(
        key="ap_channel_utilization_6ghz",
        name="6 GHz channel utilization",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="ap_channel_utilization_6ghz",
        native_unit_of_measurement=PERCENTAGE,
        product_types={"wireless"},
    ),
    MerakiDashboardSensorEntityDescription(
        key="switch_total_ports",
        name="Total ports",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="switch_total_ports",
        product_types={"switch"},
    ),
    MerakiDashboardSensorEntityDescription(
        key="switch_connected_ports",
        name="Connected ports",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="switch_connected_ports",
        product_types={"switch"},
    ),
    MerakiDashboardSensorEntityDescription(
        key="switch_connected_clients",
        name="Switch clients",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="switch_connected_clients",
        product_types={"switch"},
    ),
    MerakiDashboardSensorEntityDescription(
        key="switch_active_poe_ports",
        name="Active PoE ports",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="switch_active_poe_ports",
        product_types={"switch"},
    ),
    MerakiDashboardSensorEntityDescription(
        key="appliance_clients",
        name="Firewall clients",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="appliance_clients",
        product_types={"appliance"},
    ),
    MerakiDashboardSensorEntityDescription(
        key="appliance_performance_score",
        name="Performance score",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="appliance_performance_score",
        product_types={"appliance"},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MerakiDashboardConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Meraki Dashboard diagnostic sensors."""
    coordinator = config_entry.runtime_data
    async_add_entities([MerakiDashboardTopologySensor(coordinator)])
    tracked_unique_ids: set[str] = set()

    @callback
    def async_add_new_entities() -> None:
        entities: list[MerakiDashboardInfrastructureSensor] = []
        for serial, device in coordinator.data.infrastructure_devices.items():
            for description in SENSORS:
                if (
                    description.product_types is not None
                    and device.product_type not in description.product_types
                ):
                    continue
                unique_id = f"{serial}_{description.key}"
                if unique_id in tracked_unique_ids:
                    continue
                tracked_unique_ids.add(unique_id)
                entities.append(
                    MerakiDashboardInfrastructureSensor(
                        coordinator=coordinator,
                        serial=serial,
                        description=description,
                    )
                )

        if entities:
            async_add_entities(entities)

    async_add_new_entities()
    config_entry.async_on_unload(coordinator.async_add_listener(async_add_new_entities))


class MerakiDashboardInfrastructureSensor(
    CoordinatorEntity[MerakiDashboardDataUpdateCoordinator], SensorEntity
):
    """Diagnostic sensor bound to a Meraki infrastructure device."""

    _attr_has_entity_name = True
    entity_description: MerakiDashboardSensorEntityDescription

    def __init__(
        self,
        coordinator: MerakiDashboardDataUpdateCoordinator,
        serial: str,
        description: MerakiDashboardSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._serial = serial
        self.entity_description = description
        self._attr_unique_id = f"{serial}_{description.key}"

    @property
    def _device(self) -> MerakiDashboardInfrastructureDevice | None:
        """Return current device data."""
        return self.coordinator.data.infrastructure_devices.get(self._serial)

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return self._device is not None and super().available

    @property
    def native_value(self) -> str | int | float | None:
        """Return sensor value."""
        if (device := self._device) is None:
            return None
        value: Any = getattr(device, self.entity_description.value_key)
        if value is None:
            return None
        if isinstance(value, str | int | float):
            return value
        return str(value)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return linked device info."""
        if (device := self._device) is None:
            return None
        connections = set()
        if device.mac:
            connections.add((CONNECTION_NETWORK_MAC, device.mac))
        return DeviceInfo(
            identifiers={(DOMAIN, device.serial)},
            connections=connections,
            manufacturer="Cisco Meraki",
            model=device.model,
            name=device.name or device.serial,
        )


class MerakiDashboardTopologySensor(
    CoordinatorEntity[MerakiDashboardDataUpdateCoordinator], SensorEntity
):
    """Topology graph data for Meraki devices and clients."""

    _attr_has_entity_name = True
    _attr_name = "Topology nodes"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:graph-outline"

    def __init__(self, coordinator: MerakiDashboardDataUpdateCoordinator) -> None:
        """Initialize the topology sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.network_id}_topology"

    @property
    def native_value(self) -> int:
        """Return number of nodes in the current topology."""
        nodes, _ = self._build_topology()
        return len(nodes)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return topology graph data."""
        nodes, edges = self._build_topology()
        return {"nodes": nodes, "edges": edges}

    def _build_topology(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Build nodes and edges for topology rendering."""
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        node_ids: set[str] = set()
        edge_ids: set[tuple[str, str, str]] = set()
        infra_by_serial = self.coordinator.data.infrastructure_devices
        lan_ip_to_serial = {
            device.lan_ip: serial
            for serial, device in infra_by_serial.items()
            if device.lan_ip
        }

        for serial, device in infra_by_serial.items():
            node_ids.add(serial)
            nodes.append(
                {
                    "id": serial,
                    "label": device.name or serial,
                    "kind": device.product_type or "infrastructure",
                    "status": device.status,
                    "serial": serial,
                }
            )

        # Build infrastructure uplink edges. We infer parent from each device
        # gateway and match it against known LAN IPs of infrastructure devices.
        for serial, device in infra_by_serial.items():
            if not device.gateway:
                continue
            if not (parent_serial := lan_ip_to_serial.get(device.gateway)):
                continue
            if parent_serial == serial:
                continue

            edge_key = (serial, parent_serial, "uplink")
            if edge_key in edge_ids:
                continue
            edge_ids.add(edge_key)

            edges.append(
                {
                    "from": serial,
                    "to": parent_serial,
                    "edge_type": "uplink",
                    "connection_type": "Uplink",
                    "gateway": device.gateway,
                }
            )

        for mac, client in self.coordinator.data.clients.items():
            client_label = (
                client.description or client.dhcp_hostname or client.mdns_name or mac
            )
            node_ids.add(mac)
            nodes.append(
                {
                    "id": mac,
                    "label": client_label,
                    "kind": "client",
                    "status": client.status,
                    "mac": mac,
                }
            )

            if not client.recent_device_serial:
                continue
            serial = client.recent_device_serial
            if serial not in node_ids:
                node_ids.add(serial)
                nodes.append(
                    {
                        "id": serial,
                        "label": client.recent_device_name or serial,
                        "kind": "upstream",
                        "status": None,
                        "serial": serial,
                    }
                )
            edge_key = (mac, serial, "access")
            if edge_key in edge_ids:
                continue
            edge_ids.add(edge_key)
            edges.append(
                {
                    "from": mac,
                    "to": serial,
                    "edge_type": "access",
                    "connection_type": client.recent_device_connection,
                    "link_speed_mbps": self._parse_link_speed_mbps(
                        client.recent_device_connection
                    ),
                    "ssid": client.ssid,
                    "vlan": client.vlan,
                    "switchport": client.switchport,
                }
            )

        return nodes, edges

    @staticmethod
    def _parse_link_speed_mbps(connection_type: str | None) -> int | None:
        """Parse link speed in Mbps from a connection type string."""
        if not connection_type:
            return None
        match = re.search(
            r"(\d+(?:\.\d+)?)\s*([GM])bps", connection_type, re.IGNORECASE
        )
        if not match:
            return None
        speed = float(match.group(1))
        unit = match.group(2).upper()
        if unit == "G":
            speed *= 1000
        return int(speed)
