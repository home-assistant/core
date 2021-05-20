"""Tests for NewsManager."""


import asyncio

import aiohttp

from homeassistant.components.news.const import DISPATCHER_NEWS_EVENT, NewsSource
from homeassistant.components.news.manager import NewsManager

from tests.common import async_mock_signal


async def test_manage_sources(hass):
    """Test manage sources."""
    manager = NewsManager(hass)
    await manager.load()
    assert manager.sources[NewsSource.ALERTS]

    await manager.register_event(NewsSource.ALERTS, "test", {"title": "lorem_ipsum"})
    assert len(manager.source_events(NewsSource.ALERTS)) == 1
    await manager.manage_sources({NewsSource.ALERTS: False})
    assert not manager.sources[NewsSource.ALERTS]
    assert len(manager.source_events(NewsSource.ALERTS)) == 0


async def test_event_registration(hass):
    """Test event registration."""
    calls = async_mock_signal(hass, DISPATCHER_NEWS_EVENT)
    manager = NewsManager(hass)
    await manager.load()
    assert manager.events == {}
    assert len(calls) == 0

    await manager.register_event("awesome", "test", {"title": "lorem_ipsum"})
    assert manager.events["awesome.test"]["title"] == "lorem_ipsum"
    assert len(calls) == 1
    assert "awesome.test" in calls[0][0]["events"]

    await manager.register_event("awesome", "test", {})
    assert len(calls) == 1  # Event is already registered


async def test_event_dismissal(hass):
    """Test event dismissal."""
    calls = async_mock_signal(hass, DISPATCHER_NEWS_EVENT)
    manager = NewsManager(hass)
    await manager.load()

    manager._data["active"] = {"test": {}}
    await manager.dismiss_event("test")
    assert len(calls) == 1

    await manager.dismiss_event("test")
    assert len(calls) == 1  # Event is not active


async def test_get_external_source_data(hass, aioclient_mock, caplog):
    """Test getting data from external source."""
    aioclient_mock.get(
        "https://example.com/valid.json",
        json={"data": "awesome"},
    )
    aioclient_mock.get(
        "https://example.com/timeout.json",
        exc=asyncio.TimeoutError,
    )
    aioclient_mock.get(
        "https://example.com/client_error.json",
        exc=aiohttp.ClientError("Test error"),
    )
    manager = NewsManager(hass)
    data = await manager.get_external_source_data(
        "https://example.com/valid.json", "awesome"
    )

    assert data["data"] == "awesome"

    data = await manager.get_external_source_data(
        "https://example.com/timeout.json", "awesome"
    )
    assert data is None
    assert (
        "Request timed out while updating the source 'awesome' from 'https://example.com/timeout.json'"
        in caplog.text
    )

    data = await manager.get_external_source_data(
        "https://example.com/client_error.json", "awesome"
    )
    assert data is None
    assert (
        "Could not update source 'awesome' from 'https://example.com/client_error.json' - Test error"
        in caplog.text
    )
