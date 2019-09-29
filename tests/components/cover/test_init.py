"""The tests for the cover platform."""

from homeassistant.components.cover import SERVICE_OPEN_COVER, SERVICE_CLOSE_COVER
from homeassistant.helpers import intent
import homeassistant.components as comps
from tests.common import async_mock_service


async def test_open_cover_intent(hass):
    """Test HassOpenCover intent."""
    result = await comps.cover.async_setup(hass, {})
    assert result

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


async def test_close_cover_intent(hass):
    """Test HassCloseCover intent."""
    result = await comps.cover.async_setup(hass, {})
    assert result

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
