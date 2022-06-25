"""The tests for the feedreader component."""
from datetime import timedelta
from unittest import mock
from unittest.mock import mock_open, patch

import pytest

from homeassistant.components import feedreader
from homeassistant.components.feedreader import (
    CONF_MAX_ENTRIES,
    CONF_URLS,
    DEFAULT_SCAN_INTERVAL,
    EVENT_FEEDREADER,
)
from homeassistant.const import CONF_SCAN_INTERVAL, EVENT_HOMEASSISTANT_START
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_capture_events, async_fire_time_changed, load_fixture

URL = "http://some.rss.local/rss_feed.xml"
VALID_CONFIG_1 = {feedreader.DOMAIN: {CONF_URLS: [URL]}}
VALID_CONFIG_2 = {feedreader.DOMAIN: {CONF_URLS: [URL], CONF_SCAN_INTERVAL: 60}}
VALID_CONFIG_3 = {feedreader.DOMAIN: {CONF_URLS: [URL], CONF_MAX_ENTRIES: 100}}
VALID_CONFIG_4 = {feedreader.DOMAIN: {CONF_URLS: [URL], CONF_MAX_ENTRIES: 5}}
VALID_CONFIG_5 = {feedreader.DOMAIN: {CONF_URLS: [URL], CONF_MAX_ENTRIES: 1}}


def load_fixture_bytes(src):
    """Return byte stream of fixture."""
    feed_data = load_fixture(src)
    raw = bytes(feed_data, "utf-8")
    return raw


@pytest.fixture(name="feed_one_event")
def fixture_feed_one_event(hass):
    """Load test feed data for one event."""
    return load_fixture_bytes("feedreader.xml")


@pytest.fixture(name="feed_two_event")
def fixture_feed_two_events(hass):
    """Load test feed data for two event."""
    return load_fixture_bytes("feedreader1.xml")


@pytest.fixture(name="feed_21_events")
def fixture_feed_21_events(hass):
    """Load test feed data for twenty one events."""
    return load_fixture_bytes("feedreader2.xml")


@pytest.fixture(name="feed_three_events")
def fixture_feed_three_events(hass):
    """Load test feed data for three events."""
    return load_fixture_bytes("feedreader3.xml")


@pytest.fixture(name="feed_atom_event")
def fixture_feed_atom_event(hass):
    """Load test feed data for atom event."""
    return load_fixture_bytes("feedreader5.xml")


@pytest.fixture(name="events")
async def fixture_events(hass):
    """Fixture that catches alexa events."""
    return async_capture_events(hass, EVENT_FEEDREADER)


@pytest.fixture(name="feed_storage", autouse=True)
def fixture_feed_storage():
    """Mock builtins.open for feedreader storage."""
    with patch("homeassistant.components.feedreader.open", mock_open(), create=True):
        yield


async def test_setup_one_feed(hass):
    """Test the general setup of this component."""
    with patch(
        "homeassistant.components.feedreader.track_time_interval"
    ) as track_method:
        assert await async_setup_component(hass, feedreader.DOMAIN, VALID_CONFIG_1)
        await hass.async_block_till_done()

        track_method.assert_called_once_with(hass, mock.ANY, DEFAULT_SCAN_INTERVAL)


async def test_setup_scan_interval(hass):
    """Test the setup of this component with scan interval."""
    with patch(
        "homeassistant.components.feedreader.track_time_interval"
    ) as track_method:
        assert await async_setup_component(hass, feedreader.DOMAIN, VALID_CONFIG_2)
        await hass.async_block_till_done()

        track_method.assert_called_once_with(hass, mock.ANY, timedelta(seconds=60))


async def test_setup_max_entries(hass):
    """Test the setup of this component with max entries."""
    assert await async_setup_component(hass, feedreader.DOMAIN, VALID_CONFIG_3)
    await hass.async_block_till_done()


async def test_feed(hass, events, feed_one_event):
    """Test simple rss feed with valid data."""
    with patch(
        "feedparser.http.get",
        return_value=feed_one_event,
    ):
        assert await async_setup_component(hass, feedreader.DOMAIN, VALID_CONFIG_2)

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


async def test_atom_feed(hass, events, feed_atom_event):
    """Test simple atom feed with valid data."""
    with patch(
        "feedparser.http.get",
        return_value=feed_atom_event,
    ):
        assert await async_setup_component(hass, feedreader.DOMAIN, VALID_CONFIG_5)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data.title == "Atom-Powered Robots Run Amok"
    assert events[0].data.description == "Some text."
    assert events[0].data.link == "http://example.org/2003/12/13/atom03"
    assert events[0].data.id == "urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a"
    assert events[0].data.updated_parsed.tm_year == 2003
    assert events[0].data.updated_parsed.tm_mon == 12
    assert events[0].data.updated_parsed.tm_mday == 13
    assert events[0].data.updated_parsed.tm_hour == 18
    assert events[0].data.updated_parsed.tm_min == 30


async def test_feed_updates(hass, events, feed_one_event, feed_two_event):
    """Test feed updates."""
    side_effect = [
        feed_one_event,
        feed_two_event,
        feed_two_event,
    ]

    with patch("feedparser.http.get", side_effect=side_effect):
        assert await async_setup_component(hass, feedreader.DOMAIN, VALID_CONFIG_2)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        assert len(events) == 1

        # Change time and fetch more entries
        future = dt_util.utcnow() + timedelta(hours=1, seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        assert len(events) == 2

        # Change time but no new entries
        future = dt_util.utcnow() + timedelta(hours=2, seconds=2)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        assert len(events) == 2


async def test_feed_default_max_length(hass, events, feed_21_events):
    """Test long feed beyond the default 20 entry limit."""
    with patch("feedparser.http.get", return_value=feed_21_events):
        assert await async_setup_component(hass, feedreader.DOMAIN, VALID_CONFIG_2)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    assert len(events) == 20


async def test_feed_max_length(hass, events, feed_21_events):
    """Test long feed beyond a configured 5 entry limit."""
    with patch("feedparser.http.get", return_value=feed_21_events):
        assert await async_setup_component(hass, feedreader.DOMAIN, VALID_CONFIG_4)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    assert len(events) == 5


async def test_feed_without_publication_date_and_title(hass, events, feed_three_events):
    """Test simple feed with entry without publication date and title."""
    with patch("feedparser.http.get", return_value=feed_three_events):
        assert await async_setup_component(hass, feedreader.DOMAIN, VALID_CONFIG_2)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    assert len(events) == 3


async def test_feed_with_unrecognized_publication_date(hass, events):
    """Test simple feed with entry with unrecognized publication date."""
    with patch(
        "feedparser.http.get", return_value=load_fixture_bytes("feedreader4.xml")
    ):
        assert await async_setup_component(hass, feedreader.DOMAIN, VALID_CONFIG_2)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    assert len(events) == 1


async def test_feed_invalid_data(hass, events):
    """Test feed with invalid data."""
    invalid_data = bytes("INVALID DATA", "utf-8")
    with patch("feedparser.http.get", return_value=invalid_data):
        assert await async_setup_component(hass, feedreader.DOMAIN, VALID_CONFIG_2)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    assert len(events) == 0


async def test_feed_parsing_failed(hass, events, caplog):
    """Test feed where parsing fails."""
    assert "Error fetching feed data" not in caplog.text

    with patch("feedparser.parse", return_value=None):
        assert await async_setup_component(hass, feedreader.DOMAIN, VALID_CONFIG_2)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    assert "Error fetching feed data" in caplog.text
    assert not events
