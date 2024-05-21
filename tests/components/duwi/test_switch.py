"""Tests for the Duwi switch entity in Home Assistant."""

import logging
from unittest.mock import patch

import pytest
from homeassistant.components.duwi import DOMAIN
from homeassistant.components.duwi.switch import DuwiSwitch
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
async def duwi_hass_config(hass: HomeAssistant):
    """Set up Duwi devices within Home Assistant."""
    _LOGGER.info("Initializing DUWI device configuration for testing.")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["test_instance"] = {
        "app_key": "test_app_key",
        "app_secret": "test_app_secret",
        "access_token": "test_access_token",
    }
    yield


@pytest.fixture(autouse=True)
def mock_dev_patcher():
    """Mock control function for the Duwi device."""
    with patch(
        "duwi_smarthome_sdk.api.control.ControlClient.control", autospec=True
    ) as mock_dev:
        yield mock_dev


@pytest.fixture
def mock_switch(hass: HomeAssistant, mock_dev_patcher):
    """Create and provide a mock Duwi switch entity."""
    return DuwiSwitch(
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
        state=True,
        available=True,
    )


@pytest.mark.usefixtures("duwi_hass_config")
async def test_turn_on(hass: HomeAssistant, mock_switch):
    """Verify the switch turns on as expected."""
    await mock_switch.async_turn_on()
    await hass.async_block_till_done()
    assert mock_switch.is_on, "Switch should be ON."


@pytest.mark.usefixtures("duwi_hass_config")
async def test_turn_off(hass: HomeAssistant, mock_switch):
    """Ensure the switch turns off correctly."""
    await mock_switch.async_turn_off()
    await hass.async_block_till_done()
    assert not mock_switch.is_on, "Switch should be OFF."
