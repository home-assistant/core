"""Tests for the iOS init file."""

import json
from unittest.mock import Mock, patch

import pytest

from homeassistant.components import ios
from homeassistant.components.ios import iOSConfigView
from homeassistant.components.ios.const import DATA_CARPLAY_CONFIG
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import mock_component


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
    """Test that the iOS config view includes carplay configuration when available."""
    # Set up iOS config
    ios_config = {"push": {"categories": []}}
    view = iOSConfigView(ios_config)

    # Mock request with app containing hass
    mock_app = {ios.KEY_HASS: hass}
    request = Mock()
    request.app = mock_app

    # Set up iOS data with carplay config
    carplay_config = {
        "enabled": True,
        "quick_access": [
            {"entity_id": "light.living_room", "display_name": "Living Room"},
        ],
    }
    hass.data[ios.DOMAIN] = {DATA_CARPLAY_CONFIG: carplay_config}

    # Test with iOS carplay data
    response = view.get(request)
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


async def test_carplay_config_setup(hass: HomeAssistant) -> None:
    """Test that carplay configuration is properly stored during setup."""
    config = {
        ios.DOMAIN: {
            "carplay": {
                "enabled": True,
                "quick_access": [
                    {
                        "entity_id": "light.living_room",
                        "display_name": "Living Room Light",
                    },
                    {"entity_id": "climate.thermostat"},
                ],
            }
        }
    }

    # Setup the component with carplay config
    await async_setup_component(hass, ios.DOMAIN, config)

    # Verify carplay config is stored correctly
    carplay_config = hass.data[ios.DOMAIN][DATA_CARPLAY_CONFIG]
    assert carplay_config["enabled"] is True
    assert carplay_config["quick_access"] == [
        {"entity_id": "light.living_room", "display_name": "Living Room Light"},
        {"entity_id": "climate.thermostat"},
    ]


async def test_carplay_config_defaults(hass: HomeAssistant) -> None:
    """Test that carplay configuration uses defaults when not specified."""
    config = {ios.DOMAIN: {}}

    # Setup the component without carplay config
    await async_setup_component(hass, ios.DOMAIN, config)

    # Verify default carplay config is applied
    carplay_config = hass.data[ios.DOMAIN][DATA_CARPLAY_CONFIG]
    assert carplay_config == {"enabled": True, "quick_access": []}


async def test_carplay_config_partial(hass: HomeAssistant) -> None:
    """Test that carplay configuration works with partial config."""
    config = {
        ios.DOMAIN: {
            "carplay": {
                "quick_access": [{"entity_id": "light.kitchen"}],
            }
        }
    }

    # Setup the component with partial carplay config
    await async_setup_component(hass, ios.DOMAIN, config)

    # Verify partial config with defaults
    carplay_config = hass.data[ios.DOMAIN][DATA_CARPLAY_CONFIG]
    assert carplay_config["enabled"] is True  # Default value
    assert carplay_config["quick_access"] == [{"entity_id": "light.kitchen"}]


async def test_carplay_config_validation_missing_fields(hass: HomeAssistant) -> None:
    """Test that carplay configuration validation catches missing required fields."""
    config = {
        ios.DOMAIN: {
            "carplay": {
                "quick_access": [
                    {"display_name": "Missing entity_id"},  # Missing entity_id
                ],
            }
        }
    }

    # Setup should fail with invalid config
    result = await async_setup_component(hass, ios.DOMAIN, config)
    assert result is False


async def test_carplay_config_validation_invalid_entity_id(hass: HomeAssistant) -> None:
    """Test that carplay configuration validation catches invalid entity IDs."""
    config = {
        ios.DOMAIN: {
            "carplay": {
                "quick_access": [
                    {"entity_id": "invalid_entity_id"},  # Invalid format
                ],
            }
        }
    }

    # Setup should fail with invalid config
    result = await async_setup_component(hass, ios.DOMAIN, config)
    assert result is False


async def test_carplay_config_optional_display_name(hass: HomeAssistant) -> None:
    """Test that carplay configuration works without optional display_name."""
    config = {
        ios.DOMAIN: {
            "carplay": {
                "quick_access": [
                    {"entity_id": "light.bedroom"},  # No display_name
                ],
            }
        }
    }

    # Setup the component
    await async_setup_component(hass, ios.DOMAIN, config)

    # Verify config without display_name works
    carplay_config = hass.data[ios.DOMAIN][DATA_CARPLAY_CONFIG]
    assert carplay_config["quick_access"] == [{"entity_id": "light.bedroom"}]
