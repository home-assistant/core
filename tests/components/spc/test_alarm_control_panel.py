"""Tests for Vanderbilt SPC component."""

from unittest.mock import AsyncMock

from pyspcwebgw.const import AreaMode

from homeassistant.const import STATE_ALARM_ARMED_AWAY, STATE_ALARM_DISARMED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_update_alarm_device(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Test that alarm panel state changes on incoming websocket data."""

    config = {"spc": {"api_url": "http://localhost/", "ws_url": "ws://localhost/"}}
    assert await async_setup_component(hass, "spc", config) is True

    await hass.async_block_till_done()

    entity_id = "alarm_control_panel.house"

    assert hass.states.get(entity_id).state == STATE_ALARM_ARMED_AWAY
    assert hass.states.get(entity_id).attributes["changed_by"] == "Sven"

    mock_area = mock_client.return_value.areas["1"]

    mock_area.mode = AreaMode.UNSET
    mock_area.last_changed_by = "Anna"

    await mock_client.call_args_list[0][1]["async_callback"](mock_area)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED
    assert hass.states.get(entity_id).attributes["changed_by"] == "Anna"
