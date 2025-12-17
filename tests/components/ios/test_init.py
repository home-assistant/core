"""Tests for the iOS init file."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import ios
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


async def test_carplay_api_with_storage_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test CarPlay API with pre-populated storage data."""
    # Pre-populate storage with test data
    hass_storage["ios.carplay_config"] = {
        "version": 1,
        "minor_version": 1,
        "key": "ios.carplay_config",
        "data": {
            "enabled": False,
            "quick_access": [{"entity_id": "light.test", "display_name": "Test Light"}],
        },
    }

    # Setup the component
    await async_setup_component(hass, ios.DOMAIN, {ios.DOMAIN: {}})

    client = await hass_client()

    # Test GET endpoint returns stored data
    resp = await client.get("/api/ios/carplay")
    assert resp.status == 200
    data = await resp.json()
    assert data == {
        "enabled": False,
        "quick_access": [{"entity_id": "light.test", "display_name": "Test Light"}],
    }

    # Test POST endpoint updates storage
    update_data = {
        "enabled": True,
        "quick_access": [
            {"entity_id": "light.kitchen", "display_name": "Kitchen Light"}
        ],
    }

    resp = await client.post("/api/ios/carplay/update", json=update_data)
    assert resp.status == 200

    # Verify data was updated in storage
    resp = await client.get("/api/ios/carplay")
    assert resp.status == 200
    data = await resp.json()
    assert data == update_data

    # Verify storage was actually written to
    assert hass_storage["ios.carplay_config"]["data"] == update_data


async def test_carplay_api_error_handling(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test CarPlay API error handling for various invalid inputs."""
    # Setup the component
    await async_setup_component(hass, ios.DOMAIN, {ios.DOMAIN: {}})

    client = await hass_client()

    # Test invalid JSON
    resp = await client.post(
        "/api/ios/carplay/update",
        data="invalid json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status == 400

    # Test non-object data
    resp = await client.post("/api/ios/carplay/update", json="not an object")
    assert resp.status == 400

    # Test invalid enabled type
    resp = await client.post("/api/ios/carplay/update", json={"enabled": "not_bool"})
    assert resp.status == 400

    # Test invalid quick_access type
    resp = await client.post(
        "/api/ios/carplay/update", json={"quick_access": "not_array"}
    )
    assert resp.status == 400

    # Test invalid quick_access item type
    resp = await client.post(
        "/api/ios/carplay/update", json={"quick_access": ["not_object"]}
    )
    assert resp.status == 400

    # Test invalid entity_id type
    resp = await client.post(
        "/api/ios/carplay/update", json={"quick_access": [{"entity_id": 123}]}
    )
    assert resp.status == 400

    # Test invalid display_name type
    resp = await client.post(
        "/api/ios/carplay/update",
        json={"quick_access": [{"entity_id": "light.test", "display_name": 123}]},
    )
    assert resp.status == 400
