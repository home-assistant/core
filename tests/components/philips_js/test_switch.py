"""Tests for the Philips TV switches."""

from haphilipsjs import PhilipsTV

from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_available_without_powerstate(
    hass: HomeAssistant,
    mock_tv: PhilipsTV,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switches are available when the power state endpoint is absent."""
    mock_tv.json_feature_supported.return_value = True
    mock_tv.powerstate = None
    mock_tv.screenstate = "Off"
    mock_tv.huelamp_power = "Off"

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (screen_state := hass.states.get("switch.philips_tv_screen_state"))
    assert screen_state.state == STATE_OFF
    assert (hue_state := hass.states.get("switch.philips_tv_ambilight_hue"))
    assert hue_state.state == STATE_OFF
