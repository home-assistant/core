"""Tests for the Philips TV media player."""

from haphilipsjs import PhilipsTV
import pytest

from homeassistant.components.philips_js.const import TV_STATE_OFF, TV_STATE_ON
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import MOCK_ENTITY_ID

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("powerstate", "screenstate", "expected_state"),
    [
        pytest.param(TV_STATE_ON, TV_STATE_OFF, STATE_ON, id="powerstate-on"),
        pytest.param("Standby", TV_STATE_ON, STATE_OFF, id="powerstate-standby"),
        pytest.param(None, TV_STATE_ON, STATE_ON, id="screenstate-on"),
        pytest.param(None, TV_STATE_OFF, STATE_OFF, id="screenstate-off"),
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
