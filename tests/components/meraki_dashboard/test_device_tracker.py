"""Test Meraki Dashboard device tracker."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.meraki_dashboard.const import (
    CONF_INCLUDED_CLIENTS,
    CONF_TRACK_BLUETOOTH_CLIENTS,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_INFRASTRUCTURE_DEVICES,
)
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_device_tracker_entities(
    hass, mock_config_entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Test Meraki Dashboard device tracker entities are created."""
    clients = [
        {
            "mac": "22:33:44:55:66:77",
            "description": "Miles phone",
            "dhcpHostname": "miles-phone",
            "status": "Online",
            "ip": "1.2.3.4",
            "ip6": "2001:db8::1",
            "manufacturer": "Apple",
            "recentDeviceName": "AP-Living",
            "recentDeviceSerial": "Q2QD-3ZAQ-N9YE",
            "recentDeviceConnection": "Wireless",
            "ssid": "Home-WiFi",
            "vlan": "400",
            "namedVlan": "IoT",
            "switchport": None,
            "lastSeen": 1700000000,
            "firstSeen": 1699990000,
        },
        {
            "mac": "AA:BB:CC:DD:EE:FF",
            "description": "Kitchen TV",
            "status": "Offline",
            "ip": "1.2.3.5",
            "manufacturer": "Samsung",
        },
    ]

    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_network_clients",
            AsyncMock(return_value=clients),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_organization_devices_statuses",
            AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_clients",
            AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_wireless_status",
            AsyncMock(return_value={"basicServiceSets": []}),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_switch_ports_statuses",
            AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_appliance_performance",
            AsyncMock(return_value=None),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    tracker_entities = [entry for entry in entities if entry.domain == "device_tracker"]
    assert len(tracker_entities) == 2

    online_entity_id = next(
        entry.entity_id
        for entry in tracker_entities
        if entry.original_name == "Miles phone"
    )
    offline_entity_id = next(
        entry.entity_id
        for entry in tracker_entities
        if entry.original_name == "Kitchen TV"
    )

    online_state = hass.states.get(online_entity_id)
    offline_state = hass.states.get(offline_entity_id)

    assert online_state is not None
    assert offline_state is not None
    assert online_state.state == "home"
    assert offline_state.state == "not_home"
    assert online_state.attributes["ip"] == "1.2.3.4"
    assert online_state.attributes["connection_type"] == "Wireless"
    assert online_state.attributes["connected_via_device_name"] == "AP-Living"
    assert online_state.attributes["connected_via_device_serial"] == "Q2QD-3ZAQ-N9YE"
    assert online_state.attributes["connected_via_ssid"] == "Home-WiFi"
    assert online_state.attributes["connected_via_vlan"] == "400"
    assert online_state.attributes["connected_via_named_vlan"] == "IoT"


async def test_device_tracker_entities_filtered_by_included_clients(
    hass, mock_config_entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Test only selected client MACs are included as device trackers."""
    clients = [
        {
            "mac": "22:33:44:55:66:77",
            "description": "Miles phone",
            "status": "Online",
            "ip": "1.2.3.4",
        },
        {
            "mac": "AA:BB:CC:DD:EE:FF",
            "description": "Kitchen TV",
            "status": "Offline",
            "ip": "1.2.3.5",
        },
    ]
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_INCLUDED_CLIENTS: ["22:33:44:55:66:77"]},
    )
    with (
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_network_clients",
            AsyncMock(return_value=clients),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_organization_devices_statuses",
            AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_clients",
            AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_wireless_status",
            AsyncMock(return_value={"basicServiceSets": []}),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_switch_ports_statuses",
            AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_appliance_performance",
            AsyncMock(return_value=None),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    tracker_entities = [entry for entry in entities if entry.domain == "device_tracker"]
    assert len(tracker_entities) == 1
    assert tracker_entities[0].original_name == "Miles phone"


async def test_bluetooth_client_creates_device_tracker_entity(
    hass, mock_config_entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Test Bluetooth clients are tracked as device tracker entities."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_BLUETOOTH_CLIENTS: True,
            CONF_TRACK_INFRASTRUCTURE_DEVICES: False,
            CONF_INCLUDED_CLIENTS: [],
        },
    )
    with (
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_network_clients",
            AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_network_bluetooth_clients",
            AsyncMock(
                return_value=[
                    {
                        "mac": "11:22:33:44:55:66",
                        "name": "Headphones",
                        "deviceName": "Bose QuietComfort 35",
                        "manufacturer": "Bose",
                        "lastSeen": 1700001000,
                    }
                ]
            ),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_organization_devices_statuses",
            AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_clients",
            AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_wireless_status",
            AsyncMock(return_value={"basicServiceSets": []}),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_switch_ports_statuses",
            AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_appliance_performance",
            AsyncMock(return_value=None),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    tracker_entities = [entry for entry in entities if entry.domain == "device_tracker"]
    assert len(tracker_entities) == 1
    assert tracker_entities[0].original_name == "Headphones"

    state = hass.states.get(tracker_entities[0].entity_id)
    assert state is not None
    assert state.state == "home"
    assert state.attributes["connection_type"] == "Bluetooth"
