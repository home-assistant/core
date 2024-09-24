"""The tests for the rss_feed_api component."""

from asyncio import AbstractEventLoop
from http import HTTPStatus

from aiohttp.test_utils import TestClient
from defusedxml import ElementTree
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


@pytest.fixture
def mock_http_client(
    event_loop: AbstractEventLoop,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> TestClient:
    """Set up test fixture."""
    loop = event_loop
    config = {
        "rss_feed_template": {
            "testfeed": {
                "title": "feed title is {{states.test.test1.state}}",
                "items": [
                    {
                        "title": "item title is {{states.test.test2.state}}",
                        "description": "desc {{states.test.test3.state}}",
                    }
                ],
            }
        }
    }

    loop.run_until_complete(async_setup_component(hass, "rss_feed_template", config))
    return loop.run_until_complete(hass_client())


async def test_get_nonexistant_feed(mock_http_client) -> None:
    """Test if we can retrieve the correct rss feed."""
    resp = await mock_http_client.get("/api/rss_template/otherfeed")
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_get_rss_feed(mock_http_client, hass: HomeAssistant) -> None:
    """Test if we can retrieve the correct rss feed."""
    hass.states.async_set("test.test1", "a_state_1")
    hass.states.async_set("test.test2", "a_state_2")
    hass.states.async_set("test.test3", "a_state_3")

    resp = await mock_http_client.get("/api/rss_template/testfeed")
    assert resp.status == HTTPStatus.OK

    text = await resp.text()

    xml = ElementTree.fromstring(text)
    feed_title = xml.find("./channel/title").text
    item_title = xml.find("./channel/item/title").text
    item_description = xml.find("./channel/item/description").text
    assert feed_title == "feed title is a_state_1"
    assert item_title == "item title is a_state_2"
    assert item_description == "desc a_state_3"
