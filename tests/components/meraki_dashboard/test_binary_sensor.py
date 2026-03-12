"""Test Meraki Dashboard binary sensors."""

from unittest.mock import AsyncMock, patch

from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_infrastructure_device_sensors(
    hass,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test binary sensors for AP, switch, and firewall devices."""
    device_statuses = [
        {
            "name": "AP-Outdoor",
            "serial": "Q2QD-3ZAQ-N9YE",
            "networkId": "L_1111",
            "status": "online",
            "productType": "wireless",
            "model": "MR44",
            "lanIp": "192.168.99.2",
        },
        {
            "name": "Core-Switch",
            "serial": "Q2SW-AAAA-BBBB",
            "networkId": "L_1111",
            "status": "offline",
            "productType": "switch",
            "model": "MS250",
            "lanIp": "192.168.99.3",
        },
        {
            "name": "MX-Firewall",
            "serial": "Q2MX-CCCC-DDDD",
            "networkId": "L_1111",
            "status": "alerting",
            "productType": "appliance",
            "model": "MX85",
            "lanIp": "192.168.99.1",
        },
        {
            "name": "Ignored-Camera",
            "serial": "Q2CM-EEEE-FFFF",
            "networkId": "L_1111",
            "status": "online",
            "productType": "camera",
            "model": "MV12",
        },
        {
            "name": "Other-Network-Switch",
            "serial": "Q2SW-OTHER-NET",
            "networkId": "L_9999",
            "status": "online",
            "productType": "switch",
            "model": "MS120",
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
    binary_sensor_entries = [
        entry for entry in entries if entry.domain == "binary_sensor"
    ]
    assert len(binary_sensor_entries) == 3

    ap_entity_id = next(
        entry.entity_id
        for entry in binary_sensor_entries
        if entry.original_name == "AP-Outdoor"
    )
    switch_entity_id = next(
        entry.entity_id
        for entry in binary_sensor_entries
        if entry.original_name == "Core-Switch"
    )
    fw_entity_id = next(
        entry.entity_id
        for entry in binary_sensor_entries
        if entry.original_name == "MX-Firewall"
    )

    ap_state = hass.states.get(ap_entity_id)
    switch_state = hass.states.get(switch_entity_id)
    fw_state = hass.states.get(fw_entity_id)

    assert ap_state is not None
    assert ap_state.state == "on"
    assert "product_type" not in ap_state.attributes
    assert "status" not in ap_state.attributes

    assert switch_state is not None
    assert switch_state.state == "off"
    assert "product_type" not in switch_state.attributes
    assert "status" not in switch_state.attributes

    assert fw_state is not None
    assert fw_state.state == "off"
    assert "product_type" not in fw_state.attributes
    assert "status" not in fw_state.attributes

    assert device_registry.async_get_device(
        identifiers={("meraki_dashboard", "Q2QD-3ZAQ-N9YE")}
    )
    assert device_registry.async_get_device(
        identifiers={("meraki_dashboard", "Q2SW-AAAA-BBBB")}
    )
    assert device_registry.async_get_device(
        identifiers={("meraki_dashboard", "Q2MX-CCCC-DDDD")}
    )
