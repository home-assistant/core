"""The tests for google-assistant init."""
import asyncio

from homeassistant.setup import async_setup_component
from homeassistant.components import google_assistant as ga

GA_API_KEY = "Agdgjsj399sdfkosd932ksd"


@asyncio.coroutine
def test_request_sync_service(aioclient_mock, hass):
    """Test that it posts to the request_sync url."""
    aioclient_mock.post(
        ga.const.REQUEST_SYNC_BASE_URL, status=200)

    yield from async_setup_component(hass, 'google_assistant', {
        'google_assistant': {
            'project_id': 'test_project',
            'api_key': GA_API_KEY
        }})

    assert aioclient_mock.call_count == 0
    yield from hass.services.async_call(ga.const.DOMAIN,
                                        ga.const.SERVICE_REQUEST_SYNC,
                                        blocking=True)

    assert aioclient_mock.call_count == 1
