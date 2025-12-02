"""Tests for the iOS init file."""

import json
from unittest.mock import Mock, patch

import pytest

from homeassistant.components import ios
from homeassistant.components.ios import iOSConfigView
from homeassistant.components.mobile_app.const import DATA_CARPLAY_CONFIG
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

    # Test without mobile_app data
    response = view.get(request)
    assert response.status == 200
    response_text = response.text
    response_data = json.loads(response_text)
    assert "push" in response_data

    # Set up mobile_app data with carplay config
    carplay_config = {
        "enabled": True,
        "quick_access": [
            {"entity_id": "light.living_room", "display_name": "Living Room"},
        ],
    }
    hass.data["mobile_app"] = {DATA_CARPLAY_CONFIG: carplay_config}

    # Test with mobile_app carplay data
    response = view.get(request)
    assert response.status == 200
    response_text = response.text
    response_data = json.loads(response_text)
    assert "carplay" in response_data
    assert response_data["carplay"]["enabled"] is True
    assert len(response_data["carplay"]["quick_access"]) == 1
