"""The tests for the Alexa component."""

from asyncio import AbstractEventLoop
import datetime
from http import HTTPStatus

from aiohttp.test_utils import TestClient
import pytest

from homeassistant.components import alexa
from homeassistant.components.alexa import const
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator

SESSION_ID = "amzn1.echo-api.session.0000000-0000-0000-0000-00000000000"
APPLICATION_ID = "amzn1.echo-sdk-ams.app.000000-d0ed-0000-ad00-000000d00ebe"
REQUEST_ID = "amzn1.echo-api.request.0000000-0000-0000-0000-00000000000"

calls = []

NPR_NEWS_MP3_URL = "https://pd.npr.org/anon.npr-mp3/npr/news/newscast.mp3"


@pytest.fixture
def alexa_client(
    event_loop: AbstractEventLoop,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> TestClient:
    """Initialize a Home Assistant server for testing this module."""
    loop = event_loop

    @callback
    def mock_service(call):
        calls.append(call)

    hass.services.async_register("test", "alexa", mock_service)

    assert loop.run_until_complete(
        async_setup_component(
            hass,
            alexa.DOMAIN,
            {
                # Key is here to verify we allow other keys in config too
                "homeassistant": {},
                "alexa": {
                    "flash_briefings": {
                        "password": "pass/abc",
                        "weather": [
                            {
                                "title": "Weekly forecast",
                                "text": "This week it will be sunny.",
                            },
                            {
                                "title": "Current conditions",
                                "text": "Currently it is 80 degrees fahrenheit.",
                            },
                        ],
                        "news_audio": {
                            "title": "NPR",
                            "audio": NPR_NEWS_MP3_URL,
                            "display_url": "https://npr.org",
                            "uid": "uuid",
                        },
                    }
                },
            },
        )
    )
    return loop.run_until_complete(hass_client())


def _flash_briefing_req(client, briefing_id, password="pass%2Fabc"):
    if password is None:
        return client.get(f"/api/alexa/flash_briefings/{briefing_id}")

    return client.get(f"/api/alexa/flash_briefings/{briefing_id}?password={password}")


async def test_flash_briefing_invalid_id(alexa_client) -> None:
    """Test an invalid Flash Briefing ID."""
    req = await _flash_briefing_req(alexa_client, 10000)
    assert req.status == HTTPStatus.NOT_FOUND
    text = await req.text()
    assert text == ""


async def test_flash_briefing_no_password(alexa_client) -> None:
    """Test for no Flash Briefing password."""
    req = await _flash_briefing_req(alexa_client, "weather", password=None)
    assert req.status == HTTPStatus.UNAUTHORIZED
    text = await req.text()
    assert text == ""


async def test_flash_briefing_invalid_password(alexa_client) -> None:
    """Test an invalid Flash Briefing password."""
    req = await _flash_briefing_req(alexa_client, "weather", password="wrongpass")
    assert req.status == HTTPStatus.UNAUTHORIZED
    text = await req.text()
    assert text == ""


async def test_flash_briefing_request_for_password(alexa_client) -> None:
    """Test for "password" Flash Briefing."""
    req = await _flash_briefing_req(alexa_client, "password")
    assert req.status == HTTPStatus.NOT_FOUND
    text = await req.text()
    assert text == ""


async def test_flash_briefing_date_from_str(alexa_client) -> None:
    """Test the response has a valid date parsed from string."""
    req = await _flash_briefing_req(alexa_client, "weather")
    assert req.status == HTTPStatus.OK
    data = await req.json()
    assert isinstance(
        datetime.datetime.strptime(
            data[0].get(const.ATTR_UPDATE_DATE), const.DATE_FORMAT
        ),
        datetime.datetime,
    )


async def test_flash_briefing_valid(alexa_client) -> None:
    """Test the response is valid."""
    data = [
        {
            "titleText": "NPR",
            "redirectionURL": "https://npr.org",
            "streamUrl": NPR_NEWS_MP3_URL,
            "mainText": "",
            "uid": "uuid",
            "updateDate": "2016-10-10T19:51:42.0Z",
        }
    ]

    req = await _flash_briefing_req(alexa_client, "news_audio")
    assert req.status == HTTPStatus.OK
    json = await req.json()
    assert isinstance(
        datetime.datetime.strptime(
            json[0].get(const.ATTR_UPDATE_DATE), const.DATE_FORMAT
        ),
        datetime.datetime,
    )
    json[0].pop(const.ATTR_UPDATE_DATE)
    data[0].pop(const.ATTR_UPDATE_DATE)
    assert json == data
