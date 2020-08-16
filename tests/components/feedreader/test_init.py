"""The tests for the feedreader component."""
from datetime import timedelta
from logging import getLogger
from os import remove
from os.path import exists
import time
import unittest
from unittest import mock

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
from homeassistant.core import callback
from homeassistant.setup import setup_component

from tests.async_mock import patch
from tests.common import get_test_home_assistant, load_fixture

_LOGGER = getLogger(__name__)

URL = "http://some.rss.local/rss_feed.xml"
VALID_CONFIG_1 = {feedreader.DOMAIN: {CONF_URLS: [URL]}}
VALID_CONFIG_2 = {feedreader.DOMAIN: {CONF_URLS: [URL], CONF_SCAN_INTERVAL: 60}}
VALID_CONFIG_3 = {feedreader.DOMAIN: {CONF_URLS: [URL], CONF_MAX_ENTRIES: 100}}


class TestFeedreaderComponent(unittest.TestCase):
    """Test the feedreader component."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        # Delete any previously stored data
        data_file = self.hass.config.path(f"{feedreader.DOMAIN}.pickle")
        if exists(data_file):
            remove(data_file)
        self.addCleanup(self.hass.stop)

    def test_setup_one_feed(self):
        """Test the general setup of this component."""
        with patch(
            "homeassistant.components.feedreader.track_time_interval"
        ) as track_method:
            assert setup_component(self.hass, feedreader.DOMAIN, VALID_CONFIG_1)
            track_method.assert_called_once_with(
                self.hass, mock.ANY, DEFAULT_SCAN_INTERVAL
            )

    def test_setup_scan_interval(self):
        """Test the setup of this component with scan interval."""
        with patch(
            "homeassistant.components.feedreader.track_time_interval"
        ) as track_method:
            assert setup_component(self.hass, feedreader.DOMAIN, VALID_CONFIG_2)
            track_method.assert_called_once_with(
                self.hass, mock.ANY, timedelta(seconds=60)
            )

    def test_setup_max_entries(self):
        """Test the setup of this component with max entries."""
        assert setup_component(self.hass, feedreader.DOMAIN, VALID_CONFIG_3)

    def setup_manager(self, feed_data, max_entries=DEFAULT_MAX_ENTRIES):
        """Set up feed manager."""
        events = []

        @callback
        def record_event(event):
            """Add recorded event to set."""
            events.append(event)

        self.hass.bus.listen(EVENT_FEEDREADER, record_event)

        # Loading raw data from fixture and plug in to data object as URL
        # works since the third-party feedparser library accepts a URL
        # as well as the actual data.
        data_file = self.hass.config.path(f"{feedreader.DOMAIN}.pickle")
        storage = StoredData(data_file)
        with patch(
            "homeassistant.components.feedreader.track_time_interval"
        ) as track_method:
            manager = FeedManager(
                feed_data, DEFAULT_SCAN_INTERVAL, max_entries, self.hass, storage
            )
            # Can't use 'assert_called_once' here because it's not available
            # in Python 3.5 yet.
            track_method.assert_called_once_with(
                self.hass, mock.ANY, DEFAULT_SCAN_INTERVAL
            )
        # Artificially trigger update.
        self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
        # Collect events.
        self.hass.block_till_done()
        return manager, events

    def test_feed(self):
        """Test simple feed with valid data."""
        feed_data = load_fixture("feedreader.xml")
        manager, events = self.setup_manager(feed_data)
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
        assert manager.last_update_successful is True

    def test_feed_updates(self):
        """Test feed updates."""
        # 1. Run
        feed_data = load_fixture("feedreader.xml")
        manager, events = self.setup_manager(feed_data)
        assert len(events) == 1
        # 2. Run
        feed_data2 = load_fixture("feedreader1.xml")
        # Must patch 'get_timestamp' method because the timestamp is stored
        # with the URL which in these tests is the raw XML data.
        with patch(
            "homeassistant.components.feedreader.StoredData.get_timestamp",
            return_value=time.struct_time((2018, 4, 30, 5, 10, 0, 0, 120, 0)),
        ):
            manager2, events2 = self.setup_manager(feed_data2)
            assert len(events2) == 1
        # 3. Run
        feed_data3 = load_fixture("feedreader1.xml")
        with patch(
            "homeassistant.components.feedreader.StoredData.get_timestamp",
            return_value=time.struct_time((2018, 4, 30, 5, 11, 0, 0, 120, 0)),
        ):
            manager3, events3 = self.setup_manager(feed_data3)
            assert len(events3) == 0

    def test_feed_default_max_length(self):
        """Test long feed beyond the default 20 entry limit."""
        feed_data = load_fixture("feedreader2.xml")
        manager, events = self.setup_manager(feed_data)
        assert len(events) == 20

    def test_feed_max_length(self):
        """Test long feed beyond a configured 5 entry limit."""
        feed_data = load_fixture("feedreader2.xml")
        manager, events = self.setup_manager(feed_data, max_entries=5)
        assert len(events) == 5

    def test_feed_without_publication_date_and_title(self):
        """Test simple feed with entry without publication date and title."""
        feed_data = load_fixture("feedreader3.xml")
        manager, events = self.setup_manager(feed_data)
        assert len(events) == 3

    def test_feed_with_unrecognized_publication_date(self):
        """Test simple feed with entry with unrecognized publication date."""
        feed_data = load_fixture("feedreader4.xml")
        manager, events = self.setup_manager(feed_data)
        assert len(events) == 1

    def test_feed_invalid_data(self):
        """Test feed with invalid data."""
        feed_data = "INVALID DATA"
        manager, events = self.setup_manager(feed_data)
        assert len(events) == 0
        assert manager.last_update_successful is True

    @mock.patch("feedparser.parse", return_value=None)
    def test_feed_parsing_failed(self, mock_parse):
        """Test feed where parsing fails."""
        data_file = self.hass.config.path(f"{feedreader.DOMAIN}.pickle")
        storage = StoredData(data_file)
        manager = FeedManager(
            "FEED DATA", DEFAULT_SCAN_INTERVAL, DEFAULT_MAX_ENTRIES, self.hass, storage
        )
        # Artificially trigger update.
        self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
        # Collect events.
        self.hass.block_till_done()
        assert manager.last_update_successful is False
