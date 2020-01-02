"""The tests for google-assistant init."""
from homeassistant.components import google_assistant as ga
from homeassistant.core import Context
from homeassistant.setup import async_setup_component

GA_API_KEY = "Agdgjsj399sdfkosd932ksd"


async def test_request_sync_service(aioclient_mock, hass):
    """Test that it posts to the request_sync url."""
    aioclient_mock.post(ga.const.REQUEST_SYNC_BASE_URL, status=200)

    await async_setup_component(
        hass,
        "google_assistant",
        {"google_assistant": {"project_id": "test_project", "api_key": GA_API_KEY}},
    )

    assert aioclient_mock.call_count == 0
    await hass.services.async_call(
        ga.const.DOMAIN,
        ga.const.SERVICE_REQUEST_SYNC,
        blocking=True,
        context=Context(user_id="123"),
    )

    assert aioclient_mock.call_count == 1
