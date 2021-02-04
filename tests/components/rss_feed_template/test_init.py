"""The tests for the rss_feed_api component."""
from defusedxml import ElementTree
import pytest

from homeassistant.const import HTTP_NOT_FOUND
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_http_client(loop, hass, hass_client):
    """Set up test fixture."""
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


async def test_get_nonexistant_feed(mock_http_client):
    """Test if we can retrieve the correct rss feed."""
    resp = await mock_http_client.get("/api/rss_template/otherfeed")
    assert resp.status == HTTP_NOT_FOUND


async def test_get_rss_feed(mock_http_client, hass):
    """Test if we can retrieve the correct rss feed."""
    hass.states.async_set("test.test1", "a_state_1")
    hass.states.async_set("test.test2", "a_state_2")
    hass.states.async_set("test.test3", "a_state_3")

    resp = await mock_http_client.get("/api/rss_template/testfeed")
    assert resp.status == 200

    text = await resp.text()

    xml = ElementTree.fromstring(text)
    assert xml[0].text == "feed title is a_state_1"
    assert xml[1][0].text == "item title is a_state_2"
    assert xml[1][1].text == "desc a_state_3"
