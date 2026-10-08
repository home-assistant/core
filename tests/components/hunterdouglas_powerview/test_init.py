"""Tests for the Hunter Douglas PowerView integration initialization and device removal."""

from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

async def test_remove_shade_device_via_websocket(
    hass: HomeAssistant, 
    device_registry: dr.DeviceRegistry, 
    hass_ws_client: WebSocketGenerator
) -> None:
    """Test removing a shade device through the supported WebSocket command structure."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="hub_123")
    config_entry.add_to_hass(hass)

    hub_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "hub_123")},
    )

    shade_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "shade_999")},
        via_device_id=hub_device.id,
    )

    # Initialize authenticated WebSocket channel session
    client = await hass_ws_client(hass)

    # Send the supported core framework device removal command
    await client.send_json(
        {
            "id": 1,
            "type": "config_entries/device/remove",
            "config_entry_id": config_entry.entry_id,
            "device_id": shade_device.id,
        }
    )
    msg = await client.receive_json()

    assert msg["success"] is True
    assert device_registry.async_get(shade_device.id) is None
    
    async def test_remove_hub_device_via_websocket_is_blocked(
    hass: HomeAssistant, 
    device_registry: dr.DeviceRegistry, 
    hass_ws_client: WebSocketGenerator
) -> None:
    """Test that attempting to remove the root Hub device fails and is explicitly blocked."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="hub_123")
    config_entry.add_to_hass(hass)

    # Register the main hub device (via_device_id remains None)
    hub_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "hub_123")},
        name="PowerView Hub",
    )

    client = await hass_ws_client(hass)

    # Dispatch the removal request targeted directly at the hub
    await client.send_json(
        {
            "id": 2,
            "type": "config_entries/device/remove",
            "config_entry_id": config_entry.entry_id,
            "device_id": hub_device.id,
        }
    )
    msg = await client.receive_json()

    # Assertions: The request must fail, and the Hub device must NOT be deleted
    assert msg["success"] is False
    assert msg["error"]["code"] == "unknown_error" or "cannot_remove"
    assert device_registry.async_get(hub_device.id) is not None
