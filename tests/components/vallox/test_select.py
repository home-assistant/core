"""Tests for Vallox number platform."""
import pytest
from vallox_websocket_api import PROFILE as VALLOX_PROFILE

from homeassistant.core import HomeAssistant

from .conftest import patch_metrics, patch_profile

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "profile,expected_state",
    [
        (VALLOX_PROFILE.HOME, "Home"),
        (VALLOX_PROFILE.AWAY, "Away"),
        (VALLOX_PROFILE.BOOST, "Boost"),
        (VALLOX_PROFILE.FIREPLACE, "Fireplace"),
    ],
)
async def test_select_profile_entitity(
    profile: VALLOX_PROFILE,
    expected_state: str,
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
):
    """Test cell state sensor in defrosting state."""
    # Act
    with patch_profile(profile=profile), patch_metrics(metrics={}):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("select.vallox_current_profile")
    assert sensor.state == expected_state
