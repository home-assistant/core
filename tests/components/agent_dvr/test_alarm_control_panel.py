"""Tests for the Agent DVR alarm control panel platform."""

from homeassistant.core import HomeAssistant

from . import init_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_alarm_panel_disarmed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the alarm panel reflects a disarmed server state."""
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("alarm_control_panel.agent_desktop")
    assert state is not None
    assert state.state == "disarmed"
