"""Tests for Duwi light entity within the Duwi integration."""

import logging
from unittest.mock import patch

import pytest
from homeassistant.components.duwi import DOMAIN
from homeassistant.components.duwi.light import DuwiLight
from homeassistant.components.light import ColorMode
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


# Setup a fixture to initialize Home Assistant with test data for Duwi
@pytest.fixture
async def duwi_hass_config(hass: HomeAssistant):
    """Fixture to preconfigure Home Assistant for Duwi device testing."""
    _LOGGER.debug("Setting up Home Assistant test config for Duwi")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["test_instance"] = {
        "app_key": "test_app_key",
        "app_secret": "test_app_secret",
        "access_token": "test_access_token",
    }
    yield


# Autouse fixture to mock device control functions
@pytest.fixture(autouse=True)
def mock_dev_patcher():
    """Fixture that mocks out the Duwi device control API calls."""
    with patch(
        "duwi_smarthome_sdk.api.control.ControlClient.control", autospec=True
    ) as mock_dev:
        yield mock_dev


# Fixture to create and return a mock DuwiLight entity
@pytest.fixture
def mock_light(hass: HomeAssistant, mock_dev_patcher):
    """Generate a mock DuwiLight entity."""
    return DuwiLight(
        hass=hass,
        instance_id="test_instance",
        unique_id="unique_id",
        device_name="device_name",
        device_no="device_no",
        house_no="house_no",
        room_name="room_name",
        floor_name="floor_name",
        terminal_sequence="terminal_sequence",
        route_num="route_num",
        light_type="light_type",
        effect_list=[],
        effect_map={},
        state=True,
        available=True,
        supported_color_modes={ColorMode.COLOR_TEMP, ColorMode.HS},
    )


# Tests for validating interaction with the light entity
@pytest.mark.usefixtures("duwi_hass_config")
async def test_turn_on(hass: HomeAssistant, mock_light):
    """Test that the light turns on successfully."""
    light = mock_light
    await light.async_turn_on()  # Call turn on method
    await hass.async_block_till_done()  # Ensure all async methods have completed
    assert light.is_on  # Verify state of 'is_on' to be True


@pytest.mark.usefixtures("duwi_hass_config")
async def test_turn_off(hass: HomeAssistant, mock_light):
    """Test that the light turns off successfully."""
    light = mock_light
    await light.async_turn_off()  # Call turn off method
    await hass.async_block_till_done()  # Ensure all async methods have completed
    assert not light.is_on  # Verify state of 'is_on' to be False
