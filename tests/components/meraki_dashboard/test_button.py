"""Test Meraki Dashboard action buttons."""

from unittest.mock import AsyncMock, patch

from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_infrastructure_buttons(
    hass, mock_config_entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Test reboot and ping buttons for infrastructure devices."""
    device_statuses = [
        {
            "name": "AP-Outdoor",
            "serial": "Q2QD-3ZAQ-N9YE",
            "networkId": "L_1111",
            "status": "online",
            "productType": "wireless",
            "model": "MR44",
            "lanIp": "192.168.99.2",
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
        patch(
            "homeassistant.components.meraki_dashboard.api.MerakiDashboardApi.async_reboot_device",
            AsyncMock(return_value={"success": True}),
        ) as mock_reboot,
        patch(
            "homeassistant.components.meraki_dashboard.api.MerakiDashboardApi.async_ping_device",
            AsyncMock(return_value={"status": "queued"}),
        ) as mock_ping,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        entries = er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        reboot_button = next(
            entry
            for entry in entries
            if entry.domain == "button" and entry.original_name == "Reboot"
        )
        ping_button = next(
            entry
            for entry in entries
            if entry.domain == "button" and entry.original_name == "Ping"
        )

        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": reboot_button.entity_id},
            blocking=True,
        )
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": ping_button.entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_reboot.assert_awaited_once_with("Q2QD-3ZAQ-N9YE")
    mock_ping.assert_awaited_once_with("Q2QD-3ZAQ-N9YE")
