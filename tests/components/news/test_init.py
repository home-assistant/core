"""Test the init file of the news integration."""


from unittest.mock import Mock, patch

from homeassistant.components.news.const import DISPATCHER_NEWS_EVENT, DOMAIN
from homeassistant.components.news.manager import NewsManager
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

from tests.common import async_mock_signal


async def test_setup(hass):
    """Test setup of the integration."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    assert DOMAIN in hass.data


async def test_websocket(hass, hass_ws_client):
    """Test websocekt commands."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    manager: NewsManager = hass.data[DOMAIN]

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json({"id": 1, "type": "news"})
    response = await ws_client.receive_json()
    assert response["success"]
    assert response["result"]["sources"]["alerts"]

    assert manager.sources["alerts"]
    await ws_client.send_json(
        {"id": 2, "type": "news/sources", "sources": {"alerts": False}}
    )
    response = await ws_client.receive_json()
    assert response["success"]
    assert not manager.sources["alerts"]

    await ws_client.send_json(
        {"id": 3, "type": "news/dismiss_event", "event_key": "lorem_ipsum"}
    )
    response = await ws_client.receive_json()
    assert response["success"]

    await ws_client.send_json({"id": 4, "type": "news/subscribe"})
    response = await ws_client.receive_json()
    assert response["success"]

    calls = async_mock_signal(hass, DISPATCHER_NEWS_EVENT)
    async_dispatcher_send(hass, DISPATCHER_NEWS_EVENT, {"lorem": "ipsum"})

    response = await ws_client.receive_json()
    assert response["event"]["lorem"] == "ipsum"
    assert len(calls) == 1


async def test_register_news_event(hass):
    """Test the register_news_event function."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    manager: NewsManager = hass.data[DOMAIN]

    with patch(
        "homeassistant.helpers.frame.extract_stack",
        return_value=[
            Mock(
                filename="homeassistant/components/awesome/__init__.py",
                lineno="1337",
                line="self.do.awesome.stuff()",
            ),
        ],
    ):
        await hass.components.news.register_news_event(
            hass, "lorem_ipsum", {"title": "test"}
        )
        assert "integration.awesome.lorem_ipsum" in manager.events

    with patch(
        "homeassistant.helpers.frame.extract_stack",
        return_value=[
            Mock(
                filename="custom_components/awesome_custom/__init__.py",
                lineno="1337",
                line="self.do.awesome.stuff()",
            ),
        ],
    ):
        await hass.components.news.register_news_event(hass, "lorem_ipsum", {})
        assert "integration.awesome_custom.lorem_ipsum" not in manager.events


async def test_register_news_event_custom(hass):
    """Test the register_news_event function from a custom integration."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    manager: NewsManager = hass.data[DOMAIN]

    with patch(
        "homeassistant.helpers.frame.extract_stack",
        return_value=[
            Mock(
                filename="custom_components/awesome/__init__.py",
                lineno="1337",
                line="self.do.awesome.stuff()",
            ),
        ],
    ):
        await hass.components.news.register_news_event(hass, "lorem_ipsum", {})
        assert manager.events == {}
