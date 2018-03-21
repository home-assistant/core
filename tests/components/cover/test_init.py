"""The tests for the cover platform."""
import asyncio

from homeassistant.setup import setup_component
from homeassistant.components.cover import (SERVICE_OPEN_COVER,
                                            SERVICE_CLOSE_COVER)
from homeassistant.components import intent
import homeassistant.components as comps
#import homeassistant.util.dt as dt_util
from tests.common import get_test_home_assistant

from tests.common import async_mock_service


@asyncio.coroutine
def test_open_cover_intent(hass):
    """Test HassOpenCover intent
    """
    result = yield from comps.cover.async_setup(hass, {})
    assert result

    hass.states.async_set('cover.garage_door', 'closed')
    calls = async_mock_service(hass, 'cover', SERVICE_OPEN_COVER)

    response = yield from intent.async_handle(
        hass, 'test', 'HassOpenCover', {'name': {'value': 'garage door'}}
    )
    yield from hass.async_block_till_done()

    assert response.speech['plain']['speech'] == 'Opened garage door'
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == 'cover'
    assert call.service == 'open_cover'
    assert call.data == {'entity_id': 'cover.garage_door'}

@asyncio.coroutine
def test_close_cover_intent(hass):
    """Test HassCloseCover intent
    """
    result = yield from comps.cover.async_setup(hass, {})
    assert result

    hass.states.async_set('cover.garage_door', 'open')
    calls = async_mock_service(hass, 'cover', SERVICE_CLOSE_COVER)

    response = yield from intent.async_handle(
        hass, 'test', 'HassCloseCover', {'name': {'value': 'garage door'}}
    )
    yield from hass.async_block_till_done()

    assert response.speech['plain']['speech'] == 'Closed garage door'
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == 'cover'
    assert call.service == 'close_cover'
    assert call.data == {'entity_id': 'cover.garage_door'}
