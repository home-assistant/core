"""Tests for the Philips TV media player."""

from haphilipsjs import PhilipsTV
import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import MOCK_ENTITY_ID

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("powerstate", "screenstate", "expected_state"),
    [
        pytest.param("On", "Off", STATE_ON, id="powerstate-on"),
        pytest.param("Standby", "On", STATE_OFF, id="powerstate-standby"),
        pytest.param(None, "On", STATE_ON, id="screenstate-on"),
        pytest.param(None, "Off", STATE_OFF, id="screenstate-off"),
    ],
)
async def test_state(
    hass: HomeAssistant,
    mock_tv: PhilipsTV,
    mock_config_entry: MockConfigEntry,
    powerstate: str | None,
    screenstate: str,
    expected_state: str,
) -> None:
    """Test the media player state."""
    mock_tv.json_feature_supported.return_value = False
    mock_tv.powerstate = powerstate
    mock_tv.screenstate = screenstate

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(MOCK_ENTITY_ID))
    assert state.state == expected_state
