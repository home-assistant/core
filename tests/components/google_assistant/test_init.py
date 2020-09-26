"""The tests for google-assistant init."""
from homeassistant.components import google_assistant as ga
from homeassistant.core import Context
from homeassistant.setup import async_setup_component

from .test_http import DUMMY_CONFIG


async def test_request_sync_service(aioclient_mock, hass):
    """Test that it posts to the request_sync url."""
    aioclient_mock.post(
        ga.const.HOMEGRAPH_TOKEN_URL,
        status=200,
        json={"access_token": "1234", "expires_in": 3600},
    )

    aioclient_mock.post(ga.const.REQUEST_SYNC_BASE_URL, status=200)

    await async_setup_component(
        hass,
        "google_assistant",
        {"google_assistant": DUMMY_CONFIG},
    )

    assert aioclient_mock.call_count == 0
    await hass.services.async_call(
        ga.const.DOMAIN,
        ga.const.SERVICE_REQUEST_SYNC,
        blocking=True,
        context=Context(user_id="123"),
    )

    assert aioclient_mock.call_count == 2  # token + request
