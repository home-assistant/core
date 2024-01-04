"""The tests for the cover platform."""
import asyncio

from homeassistant.components.cover import (
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    intent as cover_intent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from tests.common import async_mock_service


async def test_open_cover_intent(hass: HomeAssistant) -> None:
    """Test HassOpenCover intent."""
    await cover_intent.async_setup_intents(hass)

    hass.states.async_set("cover.garage_door", "closed")
    calls = async_mock_service(hass, "cover", SERVICE_OPEN_COVER)

    response = await intent.async_handle(
        hass, "test", "HassOpenCover", {"name": {"value": "garage door"}}
    )
    await hass.async_block_till_done()

    assert response.speech["plain"]["speech"] == "Opened garage door"
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "cover"
    assert call.service == "open_cover"
    assert call.data == {"entity_id": "cover.garage_door"}


async def test_close_cover_intent(hass: HomeAssistant) -> None:
    """Test HassCloseCover intent."""
    await cover_intent.async_setup_intents(hass)

    hass.states.async_set("cover.garage_door", "open")
    calls = async_mock_service(hass, "cover", SERVICE_CLOSE_COVER)

    response = await intent.async_handle(
        hass, "test", "HassCloseCover", {"name": {"value": "garage door"}}
    )
    await hass.async_block_till_done()

    assert response.speech["plain"]["speech"] == "Closed garage door"
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "cover"
    assert call.service == "close_cover"
    assert call.data == {"entity_id": "cover.garage_door"}


async def test_stop_cover_intent(hass: HomeAssistant) -> None:
    """Test HassStopCover intent."""
    await cover_intent.async_setup_intents(hass)

    hass.states.async_set("cover.bedroom_shutter", "open")
    hass.states.async_set(
        "cover.bedroom_shutter",
        attributes={"current_position": 100, "supported_features": 15},
    )
    calls = async_mock_service(hass, "cover", SERVICE_STOP_COVER)

    response = await intent.async_handle(
        hass, "test", "HassCloseCover", {"name": {"value": "bedroom shutter"}}
    )
    await asyncio.sleep(2)
    response = await intent.async_handle(
        hass, "test", "HassStopCover", {"name": {"value": "bedroom shutter"}}
    )
    await hass.async_block_till_done()

    assert response.speech["plain"]["speech"] == "Stopped bedroom shutter"
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "cover"
    assert call.service == "stop_cover"
    assert call.data == {"entity_id": "cover.bedroom_shutter"}
    assert hass.states.get("cover.bedroom_shutter").attributes["current_position"] < 100


async def test_set_cover_position_intent(hass: HomeAssistant) -> None:
    """Test HassSetCoverPosition intent."""
    await cover_intent.async_setup_intents(hass)

    hass.states.async_set("cover.bedroom_shutter", "open")
    hass.states.async_set(
        "cover.bedroom_shutter",
        attributes={"current_position": 100, "supported_features": 15},
    )
    calls = async_mock_service(hass, "cover", SERVICE_SET_COVER_POSITION)

    response = await intent.async_handle(
        hass,
        "test",
        "HassSetCoverPosition",
        {"name": {"value": "bedroom shutter"}, "position": 50},
    )
    await hass.async_block_till_done()

    assert response.speech["plain"]["speech"] == "Positioned bedroom shutter"
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "cover"
    assert call.service == "set_cover_position"
    assert call.data == {"entity_id": "cover.bedroom_shutter"}
    assert hass.states.get("cover.bedroom_shutter").attributes["current_position"] < 50
