"""The tests for the feedreader component."""
from datetime import timedelta
from os import remove
from os.path import exists
import time
from unittest import mock
from unittest.mock import patch

import pytest

from homeassistant.components import feedreader
from homeassistant.components.feedreader import (
    CONF_MAX_ENTRIES,
    CONF_URLS,
    DEFAULT_MAX_ENTRIES,
    DEFAULT_SCAN_INTERVAL,
    EVENT_FEEDREADER,
    FeedManager,
    StoredData,
)
from homeassistant.const import CONF_SCAN_INTERVAL, EVENT_HOMEASSISTANT_START
from homeassistant.setup import async_setup_component

from tests.common import async_capture_events, load_fixture

URL = "http://some.rss.local/rss_feed.xml"
VALID_CONFIG_1 = {feedreader.DOMAIN: {CONF_URLS: [URL]}}
VALID_CONFIG_2 = {feedreader.DOMAIN: {CONF_URLS: [URL], CONF_SCAN_INTERVAL: 60}}
VALID_CONFIG_3 = {feedreader.DOMAIN: {CONF_URLS: [URL], CONF_MAX_ENTRIES: 100}}


@pytest.fixture(name="feed_storage")
def fixture_feed_storage(hass):
    """Create storage account for feedreader."""
    data_file = hass.config.path(f"{feedreader.DOMAIN}.pickle")
    storage = StoredData(data_file)

    yield storage

    if exists(data_file):
        remove(data_file)


async def test_setup_one_feed(hass):
    """Test the general setup of this component."""
    with patch(
        "homeassistant.components.feedreader.async_track_time_interval"
    ) as track_method:
        assert await async_setup_component(hass, feedreader.DOMAIN, VALID_CONFIG_1)
        await hass.async_block_till_done()

        track_method.assert_called_once_with(hass, mock.ANY, DEFAULT_SCAN_INTERVAL)


async def test_setup_scan_interval(hass):
    """Test the setup of this component with scan interval."""
    with patch(
        "homeassistant.components.feedreader.async_track_time_interval"
    ) as track_method:
        assert await async_setup_component(hass, feedreader.DOMAIN, VALID_CONFIG_2)
        await hass.async_block_till_done()

        track_method.assert_called_once_with(hass, mock.ANY, timedelta(seconds=60))


async def test_setup_max_entries(hass):
    """Test the setup of this component with max entries."""
    assert await async_setup_component(hass, feedreader.DOMAIN, VALID_CONFIG_3)
    await hass.async_block_till_done()


@pytest.fixture(name="events")
def fixture_events(hass):
    """Fixture that catches alexa events."""
    return async_capture_events(hass, EVENT_FEEDREADER)


async def test_feed(hass, events, feed_storage):
    """Test simple feed with valid data."""
    feed_data = load_fixture("feedreader.xml")
    max_entries = DEFAULT_MAX_ENTRIES

    FeedManager(feed_data, DEFAULT_SCAN_INTERVAL, max_entries, hass, feed_storage)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data.title == "Title 1"
    assert events[0].data.description == "Description 1"
    assert events[0].data.link == "http://www.example.com/link/1"
    assert events[0].data.id == "GUID 1"
    assert events[0].data.published_parsed.tm_year == 2018
    assert events[0].data.published_parsed.tm_mon == 4
    assert events[0].data.published_parsed.tm_mday == 30
    assert events[0].data.published_parsed.tm_hour == 5
    assert events[0].data.published_parsed.tm_min == 10


async def test_feed_updates(hass, events, feed_storage):
    """Test feed updates."""
    # 1. Run
    feed_data = load_fixture("feedreader.xml")
    FeedManager(
        feed_data, DEFAULT_SCAN_INTERVAL, DEFAULT_MAX_ENTRIES, hass, feed_storage
    )
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert len(events) == 1

    # 2. Run
    feed_data2 = load_fixture("feedreader1.xml")
    # Must patch 'get_timestamp' method because the timestamp is stored
    # with the URL which in these tests is the raw XML data.
    with patch(
        "homeassistant.components.feedreader.StoredData.get_timestamp",
        return_value=time.struct_time((2018, 4, 30, 5, 10, 0, 0, 120, 0)),
    ):
        FeedManager(
            feed_data2, DEFAULT_SCAN_INTERVAL, DEFAULT_MAX_ENTRIES, hass, feed_storage
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        assert len(events) == 2

    # 3. Run
    feed_data3 = load_fixture("feedreader1.xml")
    with patch(
        "homeassistant.components.feedreader.StoredData.get_timestamp",
        return_value=time.struct_time((2018, 4, 30, 5, 11, 0, 0, 120, 0)),
    ):
        FeedManager(
            feed_data3, DEFAULT_SCAN_INTERVAL, DEFAULT_MAX_ENTRIES, hass, feed_storage
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        assert len(events) == 2


async def test_feed_default_max_length(hass, events, feed_storage):
    """Test long feed beyond the default 20 entry limit."""
    feed_data = load_fixture("feedreader2.xml")
    FeedManager(
        feed_data, DEFAULT_SCAN_INTERVAL, DEFAULT_MAX_ENTRIES, hass, feed_storage
    )
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert len(events) == 20


async def test_feed_max_length(hass, events, feed_storage):
    """Test long feed beyond a configured 5 entry limit."""
    feed_data = load_fixture("feedreader2.xml")
    FeedManager(feed_data, DEFAULT_SCAN_INTERVAL, 5, hass, feed_storage)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert len(events) == 5


async def test_feed_without_publication_date_and_title(hass, events, feed_storage):
    """Test simple feed with entry without publication date and title."""
    feed_data = load_fixture("feedreader3.xml")
    FeedManager(
        feed_data, DEFAULT_SCAN_INTERVAL, DEFAULT_MAX_ENTRIES, hass, feed_storage
    )
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert len(events) == 3


async def test_feed_with_unrecognized_publication_date(hass, events, feed_storage):
    """Test simple feed with entry with unrecognized publication date."""
    feed_data = load_fixture("feedreader4.xml")
    FeedManager(
        feed_data, DEFAULT_SCAN_INTERVAL, DEFAULT_MAX_ENTRIES, hass, feed_storage
    )
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert len(events) == 1


async def test_feed_invalid_data(hass, events, feed_storage):
    """Test feed with invalid data."""
    feed_data = "INVALID DATA"
    FeedManager(
        feed_data, DEFAULT_SCAN_INTERVAL, DEFAULT_MAX_ENTRIES, hass, feed_storage
    )
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert len(events) == 0


async def test_feed_parsing_failed(hass, feed_storage):
    """Test feed where parsing fails."""
    with patch("feedparser.parse", return_value=None):
        manager = FeedManager(
            "FEED DATA", DEFAULT_SCAN_INTERVAL, DEFAULT_MAX_ENTRIES, hass, feed_storage
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        assert manager.last_update_successful is False
