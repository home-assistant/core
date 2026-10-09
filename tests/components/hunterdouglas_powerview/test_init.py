"""Tests for the Hunter Douglas PowerView integration setup and device removal."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import MOCK_MAC

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

async def test_setup_not_primary_hub(hass: HomeAssistant) -> None:
    """Test setup fails when the hub is not the primary hub."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    hub = MagicMock(hub_address="1.2.3.4", role="Secondary")
    hub.name = "PowerView Hub"

    with patch(
        "homeassistant.components.hunterdouglas_powerview.async_connect_hub",
        AsyncMock(return_value=MagicMock(hub=hub)),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == (
        "PowerView Hub (1.2.3.4) is performing role of Secondary Hub. Only the"
        " Primary Hub can manage shades"
    )

async def test_remove_shade_device_via_websocket_allowed_when_offline(
    hass: HomeAssistant, 
    device_registry: dr.DeviceRegistry, 
    hass_ws_client: WebSocketGenerator
) -> None:
    """Test removing a shade device is successful if it is missing from the physical hub."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="hub_123")
    config_entry.supports_remove_device = True
    config_entry.add_to_hass(hass)

    hub_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "hub_123")},
    )

    shade_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, 999)},
        via_device_id=hub_device.id,
    )

    # Mock runtime data structures to show the shade is GONE from the hub
    mock_coordinator = MagicMock()
    # Emulate coordinator.data.shades being empty or at least missing ID 999
    mock_coordinator.data.shades = {} 
    
    mock_runtime_data = MagicMock(coordinator=mock_coordinator)
    config_entry.runtime_data = mock_runtime_data

    client = await hass_ws_client(hass)

    # Dispatch device removal request
    await client.send_json(
        {
            "id": 1,
            "type": "config_entries/device/remove",
            "config_entry_id": config_entry.entry_id,
            "device_id": shade_device.id,
        }
    )
    msg = await client.receive_json()

    # The shade is offline/deleted from the hub, so the UI deletion must be allowed
    assert msg["success"] is True
    assert device_registry.async_get(shade_device.id) is None


async def test_remove_shade_device_via_websocket_blocked_when_online(
    hass: HomeAssistant, 
    device_registry: dr.DeviceRegistry, 
    hass_ws_client: WebSocketGenerator
) -> None:
    """Test that removing a shade device fails if it is still reported as online by the hub."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="hub_123")
    config_entry.supports_remove_device = True
    config_entry.add_to_hass(hass)

    hub_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "hub_123")},
    )

    shade_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, 111)},
        via_device_id=hub_device.id,
    )

    # Mock runtime data structures to show the shade is still ACTIVE on the hub
    mock_coordinator = MagicMock()
    # The shade ID 111 is present in the hub's payload, so it must be protected
    mock_coordinator.data.shades = {111: {"id": 111}} 
    
    mock_runtime_data = MagicMock(coordinator=mock_coordinator)
    config_entry.runtime_data = mock_runtime_data

    client = await hass_ws_client(hass)

    # Dispatch device removal request
    await client.send_json(
        {
            "id": 2,
            "type": "config_entries/device/remove",
            "config_entry_id": config_entry.entry_id,
            "device_id": shade_device.id,
        }
    )
    msg = await client.receive_json()

    # The deletion must fail because the device is still physically active on the network
    assert msg["success"] is False
    assert msg["error"]["code"] == "home_assistant_error"
    assert device_registry.async_get(shade_device.id) is not None


async def test_remove_hub_device_via_websocket_is_blocked(
    hass: HomeAssistant, 
    device_registry: dr.DeviceRegistry, 
    hass_ws_client: WebSocketGenerator
) -> None:
    """Test that attempting to remove the root Hub device fails and is explicitly blocked."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="hub_123")
    config_entry.add_to_hass(hass)

    hub_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "hub_123")},
        name="PowerView Hub",
    )

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 3,
            "type": "config_entries/device/remove",
            "config_entry_id": config_entry.entry_id,
            "device_id": hub_device.id,
        }
    )
    msg = await client.receive_json()

    assert msg["success"] is False
    assert msg["error"]["code"] == "home_assistant_error"
    assert device_registry.async_get(hub_device.id) is not None
    
