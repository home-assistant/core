"""Tests for the Agent DVR PTZ pulse-duration number platform."""

from homeassistant.core import HomeAssistant

from . import init_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_ptz_pulse_duration_default(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the pulse-duration number entity defaults to 0.4 seconds."""
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("number.agent_desktop_ptz_pulse_duration")
    assert state is not None
    assert state.state == "0.4"


async def test_ptz_pulse_duration_set(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setting a new pulse duration updates the shared runtime value."""
    entry = await init_integration(hass, aioclient_mock)

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.agent_desktop_ptz_pulse_duration", "value": 1.0},
        blocking=True,
    )

    state = hass.states.get("number.agent_desktop_ptz_pulse_duration")
    assert state.state == "1.0"
    assert entry.runtime_data.ptz_pulse_seconds == 1.0
