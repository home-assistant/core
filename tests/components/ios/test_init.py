"""Tests for the iOS CarPlay functionality."""

from typing import Any

from homeassistant.components import ios
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


async def test_carplay_get_data(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test CarPlay API GET endpoint."""
    # Setup the component
    await async_setup_component(hass, ios.DOMAIN, {ios.DOMAIN: {}})

    client = await hass_client()

    # Test GET endpoint with default data
    resp = await client.get("/api/ios/carplay")
    assert resp.status == 200
    data = await resp.json()
    assert data == {"enabled": True, "quick_access": []}


async def test_carplay_set_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test CarPlay API POST endpoint."""
    # Setup the component
    await async_setup_component(hass, ios.DOMAIN, {ios.DOMAIN: {}})

    client = await hass_client()

    # Test POST endpoint
    update_data = {
        "enabled": False,
        "quick_access": [
            {"entity_id": "light.kitchen", "display_name": "Kitchen Light"}
        ],
    }

    resp = await client.post("/api/ios/carplay/update", json=update_data)
    assert resp.status == 200

    # Verify data was updated
    resp = await client.get("/api/ios/carplay")
    assert resp.status == 200
    data = await resp.json()
    assert data == update_data

    # Verify storage was actually written to
    assert hass_storage["ios.carplay_config"]["data"] == update_data
