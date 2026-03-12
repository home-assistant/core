"""Test Meraki Dashboard diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_config_entry_diagnostics_redacts_sensitive_data(
    hass,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics redacts sensitive data."""
    clients = [
        {
            "mac": "22:33:44:55:66:77",
            "description": "Miles phone",
            "status": "Online",
            "ip": "1.2.3.4",
            "ip6": "2001:db8::1",
        }
    ]
    device_statuses = [
        {
            "name": "Core-Switch",
            "serial": "Q2SW-AAAA-BBBB",
            "mac": "b8:ab:61:e4:4e:7c",
            "networkId": "L_1111",
            "status": "online",
            "productType": "switch",
            "model": "MS250",
            "publicIp": "84.210.215.192",
            "lanIp": "192.168.2.150",
            "gateway": "192.168.2.1",
            "primaryDns": "192.168.2.2",
            "secondaryDns": "192.168.2.3",
        }
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

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["config_entry"]["data"]["api_key"] == "**REDACTED**"
    assert result["clients"]["22:33:44:55:66:77"]["ip_address"] == "**REDACTED**"
    assert result["clients"]["22:33:44:55:66:77"]["mac"] == "**REDACTED**"
    assert (
        result["infrastructure_devices"]["Q2SW-AAAA-BBBB"]["public_ip"]
        == "**REDACTED**"
    )
