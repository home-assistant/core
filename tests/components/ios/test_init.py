"""Tests for the iOS init file."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from homeassistant.components import ios
from homeassistant.components.ios import iOSConfigView
from homeassistant.components.ios.storage import (
    DATA_CARPLAY_STORAGE,
    CarPlayStore,
    get_carplay_store,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
    store = CarPlayStore(hass)
    await store.async_load()
    hass.data[DATA_CARPLAY_STORAGE] = store

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
    store = get_carplay_store(hass)
    data = await store.async_get_data()
    assert data == {"enabled": True, "quick_access": []}


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


async def test_ios_utility_functions(hass: HomeAssistant) -> None:
    """Test iOS utility functions."""
    # Set up test data
    hass.data[ios.DOMAIN] = {
        ios.ATTR_DEVICES: {
            "device1": {ios.ATTR_PUSH_ID: "push_id_1"},
            "device2": {ios.ATTR_PUSH_ID: "push_id_2"},
            "device3": {},  # No push ID
        }
    }

    # Test devices_with_push
    push_devices = ios.devices_with_push(hass)
    assert push_devices == {"device1": "push_id_1", "device2": "push_id_2"}

    # Test enabled_push_ids
    push_ids = ios.enabled_push_ids(hass)
    assert set(push_ids) == {"push_id_1", "push_id_2"}

    # Test devices
    all_devices = ios.devices(hass)
    assert len(all_devices) == 3

    # Test device_name_for_push_id
    device_name = ios.device_name_for_push_id(hass, "push_id_1")
    assert device_name == "device1"

    device_name = ios.device_name_for_push_id(hass, "nonexistent")
    assert device_name is None


async def test_ios_push_config_view(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test iOS push configuration view."""
    push_config = {
        "categories": [{"name": "test", "identifier": "test", "actions": []}]
    }

    # Setup the component with push config
    await async_setup_component(hass, ios.DOMAIN, {ios.DOMAIN: {"push": push_config}})

    client = await hass_client()

    # Test push config endpoint
    resp = await client.get("/api/ios/push")
    assert resp.status == 200
    data = await resp.json()
    assert data == push_config


async def test_ios_identify_device_view(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, tmp_path: Path
) -> None:
    """Test iOS device identification view."""
    config_file = tmp_path / ".ios.conf"

    # Set up initial data in hass
    hass.data[ios.DOMAIN] = {ios.ATTR_DEVICES: {}}

    # Setup the component
    await async_setup_component(hass, ios.DOMAIN, {ios.DOMAIN: {}})

    # Mock the config file path
    with patch.object(hass.config, "path", return_value=str(config_file)):
        client = await hass_client()

        device_data = {
            ios.ATTR_DEVICE_ID: "test_device_id",
            ios.ATTR_DEVICE: {
                ios.ATTR_DEVICE_NAME: "Test Device",
                ios.ATTR_DEVICE_LOCALIZED_MODEL: "iPhone",
                ios.ATTR_DEVICE_MODEL: "iPhone15,2",
                ios.ATTR_DEVICE_PERMANENT_ID: "ABC123",
                ios.ATTR_DEVICE_SYSTEM_VERSION: "17.0",
                ios.ATTR_DEVICE_TYPE: "Phone",
                ios.ATTR_DEVICE_SYSTEM_NAME: "iOS",
            },
            ios.ATTR_BATTERY: {
                ios.ATTR_BATTERY_LEVEL: 85,
                ios.ATTR_BATTERY_STATE: "Unplugged",
            },
            ios.ATTR_PUSH_TOKEN: "test_token",
            ios.ATTR_APP: {
                ios.ATTR_APP_BUNDLE_IDENTIFIER: "io.robbie.HomeAssistant",
                ios.ATTR_APP_BUILD_NUMBER: 1234,
                ios.ATTR_APP_VERSION_NUMBER: "2023.1",
            },
            ios.ATTR_PERMISSIONS: ["location", "notifications"],
            ios.ATTR_PUSH_ID: "test_push_id",
        }

        # Test device identification
        resp = await client.post("/api/ios/identify", json=device_data)
        assert resp.status == 200
        result = await resp.json()
        assert result["status"] == "registered"

        # Verify device was stored
        assert "test_device_id" in hass.data[ios.DOMAIN][ios.ATTR_DEVICES]
        stored_device = hass.data[ios.DOMAIN][ios.ATTR_DEVICES]["test_device_id"]
        assert ios.ATTR_LAST_SEEN_AT in stored_device

        # Test invalid JSON
        resp = await client.post(
            "/api/ios/identify",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400


async def test_ios_identify_device_save_error(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, tmp_path: Path
) -> None:
    """Test iOS device identification view with save error."""
    config_file = tmp_path / ".ios.conf"

    # Set up initial data in hass
    hass.data[ios.DOMAIN] = {ios.ATTR_DEVICES: {}}

    # Setup the component
    await async_setup_component(hass, ios.DOMAIN, {ios.DOMAIN: {}})

    # Mock the config file path and save_json to raise an error
    with (
        patch.object(hass.config, "path", return_value=str(config_file)),
        patch(
            "homeassistant.components.ios.save_json",
            side_effect=HomeAssistantError("Save failed"),
        ),
    ):
        client = await hass_client()

        device_data = {
            ios.ATTR_DEVICE_ID: "test_device_id",
            ios.ATTR_DEVICE: {
                ios.ATTR_DEVICE_NAME: "Test Device",
                ios.ATTR_DEVICE_LOCALIZED_MODEL: "iPhone",
                ios.ATTR_DEVICE_MODEL: "iPhone15,2",
                ios.ATTR_DEVICE_PERMANENT_ID: "ABC123",
                ios.ATTR_DEVICE_SYSTEM_VERSION: "17.0",
                ios.ATTR_DEVICE_TYPE: "Phone",
                ios.ATTR_DEVICE_SYSTEM_NAME: "iOS",
            },
            ios.ATTR_BATTERY: {
                ios.ATTR_BATTERY_LEVEL: 85,
                ios.ATTR_BATTERY_STATE: "Unplugged",
            },
            ios.ATTR_PUSH_TOKEN: "test_token",
            ios.ATTR_APP: {
                ios.ATTR_APP_BUNDLE_IDENTIFIER: "io.robbie.HomeAssistant",
                ios.ATTR_APP_BUILD_NUMBER: 1234,
                ios.ATTR_APP_VERSION_NUMBER: "2023.1",
            },
            ios.ATTR_PERMISSIONS: ["location", "notifications"],
            ios.ATTR_PUSH_ID: "test_push_id",
        }

        # Test device identification with save error
        resp = await client.post("/api/ios/identify", json=device_data)
        assert resp.status == 500
        result = await resp.json()
        assert result["message"] == "Error saving device."
