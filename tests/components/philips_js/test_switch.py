"""Tests for the Philips TV switches."""

from haphilipsjs import PhilipsTV
import pytest

from homeassistant.components.philips_js.const import TV_STATE_OFF
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("entity_id", "screenstate", "huelamp_power"),
    [
        pytest.param(
            "switch.philips_tv_screen_state",
            TV_STATE_OFF,
            None,
            id="screen",
        ),
        pytest.param(
            "switch.philips_tv_ambilight_hue",
            None,
            TV_STATE_OFF,
            id="ambilight-hue",
        ),
    ],
)
async def test_available_without_powerstate(
    hass: HomeAssistant,
    mock_tv: PhilipsTV,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    screenstate: str | None,
    huelamp_power: str | None,
) -> None:
    """Test switches are available when the power state endpoint is absent."""
    mock_tv.json_feature_supported.return_value = True
    mock_tv.powerstate = None
    mock_tv.screenstate = screenstate
    mock_tv.huelamp_power = huelamp_power

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF
