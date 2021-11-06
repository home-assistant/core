"""Tests for SpeedTest button."""
from unittest.mock import MagicMock

from homeassistant.components import speedtestdotnet
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button.const import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, EVENT_STATE_CHANGED, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_capture_events
from tests.components.speedtestdotnet import MOCK_RESULTS


async def test_speedtestdotnet_button(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test button created for speedtestdotnet integration."""
    entry = MockConfigEntry(domain=speedtestdotnet.DOMAIN, data={})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("button.speedtest_run_now")

    assert state
    assert state.state == STATE_UNKNOWN

    mock_api.return_value.results.dict.return_value = {
        **MOCK_RESULTS,
        "download": 2048000,
    }
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.speedtest_run_now"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(events) == 2
    assert events[0].data.get("entity_id") == "button.speedtest_run_now"
    assert events[1].data.get("entity_id") == "sensor.speedtest_download"
