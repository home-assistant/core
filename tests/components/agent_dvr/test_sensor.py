"""Tests for the Agent DVR event-count sensor platform."""

from homeassistant.core import HomeAssistant

from . import init_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_events_24h(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the 24h event-count sensor reads the eventcounts.json response."""
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("sensor.desktop_front_door_events_24h")
    assert state is not None
    assert state.state == "3"
