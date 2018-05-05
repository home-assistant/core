"""The tests for the feedreader component."""
import time
from datetime import datetime

import unittest
from genericpath import exists
from logging import getLogger
from os import remove
from unittest import mock
from unittest.mock import patch

from homeassistant.components import feedreader
from homeassistant.components.feedreader import CONF_URLS, FeedManager, \
    StoredData, EVENT_FEEDREADER
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import callback
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant, assert_setup_component, \
    load_fixture

_LOGGER = getLogger(__name__)

URL = 'http://some.rss.local/rss_feed.xml'
VALID_CONFIG_1 = {
    feedreader.DOMAIN: {
        CONF_URLS: [URL]
    }
}


class TestFeedreaderComponent(unittest.TestCase):
    """Test the feedreader component."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        # Delete any previously stored data
        data_file = self.hass.config.path("{}.pickle".format('feedreader'))
        if exists(data_file):
            remove(data_file)

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_one_feed(self):
        """Test the general setup of this component."""
        with assert_setup_component(1, 'feedreader'):
            self.assertTrue(setup_component(self.hass, feedreader.DOMAIN,
                                            VALID_CONFIG_1))

    def setup_manager(self, feed_data):
        events = []

        @callback
        def record_event(event):
            """Add recorded event to set."""
            events.append(event)

        self.hass.bus.listen(EVENT_FEEDREADER, record_event)

        # Loading raw data from fixture and plug in to data object as URL
        # works since the third-party feedparser library accepts a URL
        # as well as the actual data.
        data_file = self.hass.config.path("{}.pickle".format(
            feedreader.DOMAIN))
        storage = StoredData(data_file)
        with patch("homeassistant.components.feedreader."
                   "track_utc_time_change") as track_method:
            manager = FeedManager(feed_data, self.hass, storage)
            track_method.assert_called_once()
        # Artificially trigger update.
        self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
        # Collect events.
        self.hass.block_till_done()
        return manager, events

    def test_feed(self):
        """Test simple feed with valid data."""
        feed_data = load_fixture('feedreader.xml')
        manager, events = self.setup_manager(feed_data)
        assert len(events) == 1
        assert events[0].data.title == "Title 1"
        assert events[0].data.description == "Description 1"
        assert events[0].data.link == "http://www.example.com/link/1"
        assert events[0].data.id == "GUID 1"
        assert datetime.fromtimestamp(
            time.mktime(events[0].data.published_parsed)) == \
            datetime(2018, 4, 30, 5, 10, 0)
        assert manager.last_update_successful == True

    def test_feed_updates(self):
        """Test feed updates."""
        # 1. Run
        feed_data = load_fixture('feedreader.xml')
        manager, events = self.setup_manager(feed_data)
        assert len(events) == 1
        # 2. Run
        feed_data2 = load_fixture('feedreader1.xml')
        # Must patch 'get_timestamp' method because the timestamp is stored
        # with the URL which in these tests is the raw XML data.
        with patch("homeassistant.components.feedreader.StoredData."
                   "get_timestamp", return_value=time.struct_time(
                (2018, 4, 30, 5, 10, 0, 0, 120, 0))) as mock_get_timestamp:
            manager2, events2 = self.setup_manager(feed_data2)
            assert len(events2) == 1
        # 3. Run
        feed_data3 = load_fixture('feedreader1.xml')
        with patch("homeassistant.components.feedreader.StoredData."
                   "get_timestamp", return_value=time.struct_time(
                (2018, 4, 30, 5, 11, 0, 0, 120, 0))) as mock_get_timestamp:
            manager3, events3 = self.setup_manager(feed_data3)
            assert len(events3) == 0

    def test_feed_max_length(self):
        """Test long feed beyond the 20 entry limit."""
        feed_data = load_fixture('feedreader2.xml')
        manager, events = self.setup_manager(feed_data)
        assert len(events) == 20

    def test_feed_without_publication_date(self):
        """Test simple feed with entry without publication date."""
        feed_data = load_fixture('feedreader3.xml')
        manager, events = self.setup_manager(feed_data)
        assert len(events) == 2

    def test_feed_invalid_data(self):
        """Test feed with invalid data."""
        feed_data = "INVALID DATA"
        manager, events = self.setup_manager(feed_data)
        assert len(events) == 0
        assert manager.last_update_successful == True

    @mock.patch('feedparser.parse', return_value=None)
    def test_feed_parsing_failed(self, mock_parse):
        """Test feed where parsing fails."""
        data_file = self.hass.config.path("{}.pickle".format(
            feedreader.DOMAIN))
        storage = StoredData(data_file)
        manager = FeedManager("FEED DATA", self.hass, storage)
        # Artificially trigger update.
        self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
        # Collect events.
        self.hass.block_till_done()
        assert manager.last_update_successful == False
