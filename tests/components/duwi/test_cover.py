"""Tests for the Duwi cover entity within the Duwi integration."""

import logging
from unittest.mock import patch

import pytest
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.components.duwi import DOMAIN
from homeassistant.components.duwi.cover import DuwiCover
from homeassistant.core import HomeAssistant


_LOGGER = logging.getLogger(__name__)


@pytest.fixture
async def duwi_hass_config(hass: HomeAssistant):
    """Create a configuration fixture for Duwi within Home Assistant."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["test_instance"] = {
        "app_key": "test_app_key",
        "app_secret": "test_app_secret",
        "access_token": "test_access_token",
    }
    yield


@pytest.fixture(autouse=True)
def mock_dev_patcher():
    """Mock some Duwi device methods."""
    with patch(
        "duwi_smarthome_sdk.api.control.ControlClient.control", autospec=True
    ) as mock_dev:
        yield mock_dev


@pytest.fixture
def mock_cover(hass: HomeAssistant, mock_dev_patcher):
    """Create a mocked Duwi cover object."""
    return DuwiCover(
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
        position=10,
        supported_features=CoverEntityFeature.SET_POSITION,
    )


@pytest.mark.usefixtures("duwi_hass_config")
async def test_open_cover(hass: HomeAssistant, mock_cover):
    """Test the opening of the cover."""
    cover = mock_cover

    await cover.async_open_cover()
    await hass.async_block_till_done()

    assert cover.current_cover_position == 100


@pytest.mark.usefixtures("duwi_hass_config")
async def test_close_cover(hass: HomeAssistant, mock_cover):
    """Test the closing of the cover."""
    cover = mock_cover

    await cover.async_close_cover()
    await hass.async_block_till_done()

    assert cover.current_cover_position == 0


@pytest.mark.usefixtures("duwi_hass_config")
async def test_set_cover_position(hass: HomeAssistant, mock_cover):
    """Test adjust the cover to a specific position."""
    cover = mock_cover

    new_position = 50
    await cover.async_set_cover_position(position=new_position)
    await hass.async_block_till_done()

    assert cover.current_cover_position == new_position
