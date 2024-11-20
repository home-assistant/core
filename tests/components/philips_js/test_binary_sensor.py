"""The tests for philips_js binary_sensor."""

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import MOCK_NAME, MOCK_RECORDINGS_LIST

ID_RECORDING_AVAILABLE = (
    "binary_sensor." + MOCK_NAME.replace(" ", "_").lower() + "_new_recording_available"
)
ID_RECORDING_ONGOING = (
    "binary_sensor." + MOCK_NAME.replace(" ", "_").lower() + "_recording_ongoing"
)


@pytest.fixture
async def mock_tv_api_invalid(mock_tv):
    """Set up a invalid mock_tv with should not create sensors."""
    mock_tv.secured_transport = True
    mock_tv.api_version = 1
    mock_tv.recordings_list = None
    return mock_tv


@pytest.fixture
async def mock_tv_api_valid(mock_tv):
    """Set up a valid mock_tv with should create sensors."""
    mock_tv.secured_transport = True
    mock_tv.api_version = 6
    mock_tv.recordings_list = MOCK_RECORDINGS_LIST
    return mock_tv


@pytest.fixture
async def mock_tv_recordings_list_unavailable(mock_tv):
    """Set up a valid mock_tv with should create sensors."""
    mock_tv.secured_transport = True
    mock_tv.api_version = 6
    mock_tv.recordings_list = None
    return mock_tv


async def test_recordings_list_api_invalid(
    mock_tv_api_invalid, mock_config_entry, hass: HomeAssistant
) -> None:
    """Test if sensors are not created if mock_tv is invalid."""

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    state = hass.states.get(ID_RECORDING_AVAILABLE)
    assert state is None

    state = hass.states.get(ID_RECORDING_ONGOING)
    assert state is None


async def test_recordings_list_valid(
    mock_tv_api_valid, mock_config_entry, hass: HomeAssistant
) -> None:
    """Test if sensors are created correctly."""

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    state = hass.states.get(ID_RECORDING_AVAILABLE)
    assert state.state == STATE_ON

    state = hass.states.get(ID_RECORDING_ONGOING)
    assert state.state == STATE_ON


async def test_recordings_list_unavailable(
    mock_tv_recordings_list_unavailable, mock_config_entry, hass: HomeAssistant
) -> None:
    """Test if sensors are created correctly."""

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    state = hass.states.get(ID_RECORDING_AVAILABLE)
    assert state.state == STATE_OFF

    state = hass.states.get(ID_RECORDING_ONGOING)
    assert state.state == STATE_OFF
