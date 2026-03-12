"""Test Meraki Dashboard diagnostic sensors."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.meraki_dashboard.api import MerakiDashboardApiError
from homeassistant.const import PERCENTAGE
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_infrastructure_diagnostic_sensors(
    hass, mock_config_entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Test diagnostic sensors are created under infrastructure devices."""
    device_statuses = [
        {
            "name": "AP-Outdoor",
            "serial": "Q4CD-XAPS-SNAW",
            "mac": "b8:ab:61:e4:4e:7c",
            "networkId": "L_1111",
            "status": "online",
            "productType": "switch",
            "model": "MS130-12X",
            "publicIp": "84.210.215.192",
            "lanIp": "192.168.2.150",
            "gateway": "192.168.2.1",
            "ipType": "static",
            "primaryDns": "192.168.2.2",
            "secondaryDns": "Unknown",
            "lastReportedAt": "2026-02-16T11:04:55Z",
        }
    ]
    switch_ports_statuses = [
        {
            "portId": "1",
            "status": "Connected",
            "clientCount": 2,
            "poe": {"isAllocated": True},
        },
        {
            "portId": "2",
            "status": "Disconnected",
            "clientCount": 0,
            "poe": {"isAllocated": False},
        },
    ]

    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_network_clients",
            AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_organization_devices_statuses",
            AsyncMock(return_value=device_statuses),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_switch_ports_statuses",
            AsyncMock(return_value=switch_ports_statuses),
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
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_appliance_performance",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_organization_wireless_channel_utilization_by_device",
            AsyncMock(return_value=[]),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    sensor_entries = [entry for entry in entries if entry.domain == "sensor"]
    assert len(sensor_entries) == 18

    serial_sensor = next(
        entry.entity_id for entry in sensor_entries if entry.original_name == "Serial"
    )
    status_sensor = next(
        entry.entity_id for entry in sensor_entries if entry.original_name == "Status"
    )
    public_ip_sensor = next(
        entry.entity_id
        for entry in sensor_entries
        if entry.original_name == "Public IP"
    )
    total_ports_sensor = next(
        entry.entity_id
        for entry in sensor_entries
        if entry.original_name == "Total ports"
    )
    connected_clients_sensor = next(
        entry.entity_id
        for entry in sensor_entries
        if entry.original_name == "Switch clients"
    )

    assert hass.states.get(serial_sensor).state == "Q4CD-XAPS-SNAW"
    assert hass.states.get(status_sensor).state == "online"
    assert hass.states.get(public_ip_sensor).state == "84.210.215.192"
    assert hass.states.get(total_ports_sensor).state == "2"
    assert hass.states.get(connected_clients_sensor).state == "2"

    topology_sensor = next(
        entry.entity_id
        for entry in sensor_entries
        if entry.original_name == "Topology nodes"
    )
    topology_state = hass.states.get(topology_sensor)
    assert topology_state is not None
    assert topology_state.state == "1"
    assert topology_state.attributes["nodes"][0]["id"] == "Q4CD-XAPS-SNAW"


async def test_ap_channel_diagnostic_sensors(
    hass, mock_config_entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Test AP channel diagnostic sensors for 2.4/5/6 GHz interfaces."""
    device_statuses = [
        {
            "name": "AP-Outdoor",
            "serial": "Q2QD-3ZAQ-N9YE",
            "mac": "b8:ab:61:e4:4e:7c",
            "networkId": "L_1111",
            "status": "online",
            "productType": "wireless",
            "model": "CW9166",
        }
    ]
    wireless_status = {
        "basicServiceSets": [
            {"enabled": True, "band": "2.4 GHz", "channel": 1},
            {"enabled": True, "band": "5 GHz", "channel": 44},
            {"enabled": True, "band": "6 GHz", "channel": 37},
        ]
    }
    channel_utilization = [
        {
            "serial": "Q2QD-3ZAQ-N9YE",
            "byBand": [
                {"band": "2.4", "total": {"percentage": 21.5}},
                {"band": "5", "total": {"percentage": 34.2}},
                {"band": "6", "total": {"percentage": 17.8}},
            ],
        }
    ]

    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_network_clients",
            AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_organization_devices_statuses",
            AsyncMock(return_value=device_statuses),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_switch_ports_statuses",
            AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_clients",
            AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_wireless_status",
            AsyncMock(return_value=wireless_status),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_appliance_performance",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_organization_wireless_channel_utilization_by_device",
            AsyncMock(return_value=channel_utilization),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    sensor_entries = [entry for entry in entries if entry.domain == "sensor"]

    channel_24_sensor = next(
        entry.entity_id
        for entry in sensor_entries
        if entry.original_name == "2.4 GHz channels"
    )
    channel_5_sensor = next(
        entry.entity_id
        for entry in sensor_entries
        if entry.original_name == "5 GHz channels"
    )
    channel_6_sensor = next(
        entry.entity_id
        for entry in sensor_entries
        if entry.original_name == "6 GHz channels"
    )
    utilization_24_sensor = next(
        entry.entity_id
        for entry in sensor_entries
        if entry.original_name == "2.4 GHz channel utilization"
    )
    utilization_5_sensor = next(
        entry.entity_id
        for entry in sensor_entries
        if entry.original_name == "5 GHz channel utilization"
    )
    utilization_6_sensor = next(
        entry.entity_id
        for entry in sensor_entries
        if entry.original_name == "6 GHz channel utilization"
    )

    assert hass.states.get(channel_24_sensor).state == "1"
    assert hass.states.get(channel_5_sensor).state == "44"
    assert hass.states.get(channel_6_sensor).state == "37"
    assert hass.states.get(utilization_24_sensor).state == "21.5"
    assert hass.states.get(utilization_5_sensor).state == "34.2"
    assert hass.states.get(utilization_6_sensor).state == "17.8"
    assert (
        hass.states.get(utilization_24_sensor).attributes["unit_of_measurement"]
        == PERCENTAGE
    )


async def test_optional_device_detail_failure_does_not_break_setup(
    hass, mock_config_entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Test setup still works when optional detail endpoint fails."""
    device_statuses = [
        {
            "name": "Core-Switch",
            "serial": "Q2SW-AAAA-BBBB",
            "mac": "b8:ab:61:e4:4e:7c",
            "networkId": "L_1111",
            "status": "online",
            "productType": "switch",
            "model": "MS250",
        }
    ]

    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_network_clients",
            AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_organization_devices_statuses",
            AsyncMock(return_value=device_statuses),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_switch_ports_statuses",
            AsyncMock(side_effect=MerakiDashboardApiError("failed")),
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
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_appliance_performance",
            AsyncMock(return_value=None),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert any(
        entry.domain == "sensor" and entry.original_name == "Serial"
        for entry in entries
    )


async def test_topology_sensor_builds_uplink_chain(
    hass, mock_config_entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Test topology includes both access and uplink edges."""
    clients = [
        {
            "mac": "22:33:44:55:66:77",
            "description": "Camera-1",
            "status": "Online",
            "recentDeviceSerial": "Q2AP-AAAA-BBBB",
            "recentDeviceName": "AP-Living",
            "recentDeviceConnection": "Wireless",
            "ssid": "Home-WiFi",
            "vlan": "400",
        }
    ]
    device_statuses = [
        {
            "name": "AP-Living",
            "serial": "Q2AP-AAAA-BBBB",
            "networkId": "L_1111",
            "status": "online",
            "productType": "wireless",
            "model": "MR44",
            "lanIp": "192.168.2.20",
            "gateway": "192.168.2.1",
        },
        {
            "name": "MX-FW",
            "serial": "Q2FW-CCCC-DDDD",
            "networkId": "L_1111",
            "status": "online",
            "productType": "appliance",
            "model": "MX85",
            "lanIp": "192.168.2.1",
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
            AsyncMock(return_value=device_statuses),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_switch_ports_statuses",
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
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_device_appliance_performance",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_organization_wireless_channel_utilization_by_device",
            AsyncMock(return_value=[]),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    topology_entity = next(
        entry.entity_id
        for entry in entries
        if entry.domain == "sensor" and entry.original_name == "Topology nodes"
    )
    topology_state = hass.states.get(topology_entity)
    assert topology_state is not None
    edges = topology_state.attributes["edges"]

    assert any(
        edge["from"] == "22:33:44:55:66:77"
        and edge["to"] == "Q2AP-AAAA-BBBB"
        and edge["edge_type"] == "access"
        for edge in edges
    )
    assert any(
        edge["from"] == "Q2AP-AAAA-BBBB"
        and edge["to"] == "Q2FW-CCCC-DDDD"
        and edge["edge_type"] == "uplink"
        for edge in edges
    )
