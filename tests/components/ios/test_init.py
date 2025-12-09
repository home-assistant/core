"""Tests for the iOS init file."""

import json
from unittest.mock import Mock, patch

import pytest

from homeassistant.components import ios
from homeassistant.components.ios import iOSConfigView
from homeassistant.components.ios.storage import CarPlayStore, async_get_carplay_store
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import mock_component
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def mock_load_json():
    """Mock load_json."""
    with patch("homeassistant.components.ios.load_json_object", return_value={}):
        yield


@pytest.fixture(autouse=True)
def mock_dependencies(hass: HomeAssistant) -> None:
    """Mock dependencies loaded."""
    mock_component(hass, "zeroconf")
    mock_component(hass, "device_tracker")


async def test_creating_entry_sets_up_sensor(hass: HomeAssistant) -> None:
    """Test setting up iOS loads the sensor component."""
    with patch(
        "homeassistant.components.ios.sensor.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        assert await async_setup_component(hass, ios.DOMAIN, {ios.DOMAIN: {}})
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_configuring_ios_creates_entry(hass: HomeAssistant) -> None:
    """Test that specifying config will create an entry."""
    with patch(
        "homeassistant.components.ios.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        await async_setup_component(hass, ios.DOMAIN, {"ios": {"push": {}}})
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_not_configuring_ios_not_creates_entry(hass: HomeAssistant) -> None:
    """Test that no config will not create an entry."""
    with patch(
        "homeassistant.components.ios.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        await async_setup_component(hass, ios.DOMAIN, {"foo": "bar"})
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 0


async def test_ios_config_view_includes_carplay(hass: HomeAssistant) -> None:
    """Test that the iOS config view includes carplay configuration from storage."""
    # Set up iOS config
    ios_config = {"push": {"categories": []}}
    view = iOSConfigView(ios_config)

    # Mock request with app containing hass
    mock_app = {ios.KEY_HASS: hass}
    request = Mock()
    request.app = mock_app

    # Initialize CarPlay store with test data
    store = await async_get_carplay_store(hass)
    await store.async_set_data(
        {
            "enabled": True,
            "quick_access": [
                {"entity_id": "light.living_room", "display_name": "Living Room"},
            ],
        }
    )
    hass.data[ios.DOMAIN] = {}  # Test with iOS carplay data from storage
    response = await view.get(request)
    assert response.status == 200
    response_text = response.text
    response_data = json.loads(response_text)
    assert "push" in response_data
    assert "carplay" in response_data
    assert response_data["carplay"]["enabled"] is True
    assert len(response_data["carplay"]["quick_access"]) == 1
    assert (
        response_data["carplay"]["quick_access"][0]["entity_id"] == "light.living_room"
    )


async def test_carplay_storage_setup(hass: HomeAssistant) -> None:
    """Test that carplay storage is properly initialized during setup."""
    # Setup the component
    await async_setup_component(hass, ios.DOMAIN, {ios.DOMAIN: {}})

    # Verify carplay store is created and accessible
    assert ios.DOMAIN in hass.data

    # Verify store can be accessed through the proper function
    store = await async_get_carplay_store(hass)
    data = await store.async_get_data()
    assert data == {"enabled": True, "quick_access": []}


async def test_carplay_store_operations(hass: HomeAssistant) -> None:
    """Test CarPlay store CRUD operations."""
    store = CarPlayStore(hass)

    # Test setting and getting data
    test_data = {
        "enabled": True,
        "quick_access": [
            {"entity_id": "light.living_room", "display_name": "Living Room Light"},
            {"entity_id": "climate.thermostat"},
        ],
    }

    await store.async_set_data(test_data)
    retrieved_data = await store.async_get_data()

    assert retrieved_data == test_data

    # Test updating data
    updated_data = {
        "enabled": False,
        "quick_access": [{"entity_id": "switch.fan"}],
    }

    await store.async_set_data(updated_data)
    new_data = await store.async_get_data()

    assert new_data == updated_data


async def test_carplay_api_endpoints(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test CarPlay API endpoints."""
    # Setup the component
    await async_setup_component(hass, ios.DOMAIN, {ios.DOMAIN: {}})

    client = await hass_client()

    # Test GET endpoint
    resp = await client.get("/api/ios/carplay")
    assert resp.status == 200
    data = await resp.json()
    assert data == {"enabled": True, "quick_access": []}

    # Test POST endpoint
    update_data = {
        "enabled": True,
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


async def test_carplay_api_validation(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test CarPlay API validation."""
    # Setup the component
    await async_setup_component(hass, ios.DOMAIN, {ios.DOMAIN: {}})

    client = await hass_client()

    # Test invalid entity_id format
    invalid_data = {
        "enabled": True,
        "quick_access": [{"entity_id": "invalid_format", "display_name": "Invalid"}],
    }

    resp = await client.post("/api/ios/carplay/update", json=invalid_data)
    assert resp.status == 400

    # Test missing entity_id
    missing_entity_data = {
        "enabled": True,
        "quick_access": [{"display_name": "Missing Entity"}],
    }

    resp = await client.post("/api/ios/carplay/update", json=missing_entity_data)
    assert resp.status == 400
