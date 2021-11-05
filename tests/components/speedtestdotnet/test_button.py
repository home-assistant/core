"""Tests for SpeedTest button."""
from unittest.mock import MagicMock

from homeassistant.components import speedtestdotnet
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button.const import SERVICE_PRESS
from homeassistant.components.speedtestdotnet.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, EVENT_CALL_SERVICE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_capture_events


async def test_speedtestdotnet_button(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test button created for speedtestdotnet integration."""
    entry = MockConfigEntry(domain=speedtestdotnet.DOMAIN, data={})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(f"button.{DEFAULT_NAME}_run_now")

    assert state
    assert state.state == STATE_UNKNOWN

    events = async_capture_events(hass, EVENT_CALL_SERVICE)
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: f"button.{DEFAULT_NAME}_run_now"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(events) == 2
    assert events[0].data.get("domain") == BUTTON_DOMAIN
    assert events[1].data.get("domain") == DOMAIN
