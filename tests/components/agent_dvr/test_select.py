"""Tests for the Agent DVR PTZ preset select platform."""

from homeassistant.core import HomeAssistant

from . import init_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_ptz_preset_options(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the preset dropdown lists the camera's configured presets."""
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("select.desktop_front_door_ptz_preset")
    assert state is not None
    assert state.attributes["options"] == ["Home", "Away"]


async def test_ptz_preset_select(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test selecting a preset calls ptzpreset with the chosen name."""
    await init_integration(hass, aioclient_mock)

    aioclient_mock.get(
        "http://example.local:8090/command.cgi?cmd=ptzpreset&oid=1&ot=2&preset=Away",
        text="{}",
    )

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.desktop_front_door_ptz_preset", "option": "Away"},
        blocking=True,
    )

    state = hass.states.get("select.desktop_front_door_ptz_preset")
    assert state.state == "Away"
