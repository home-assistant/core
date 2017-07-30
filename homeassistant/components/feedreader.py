"""
Support for RSS/Atom feeds.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/feedreader/
"""
from datetime import datetime
from logging import getLogger
from os.path import exists
from threading import Lock
import pickle

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.helpers.event import track_utc_time_change
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['feedparser==5.2.1']

_LOGGER = getLogger(__name__)

CONF_URLS = 'urls'

DOMAIN = 'feedreader'

EVENT_FEEDREADER = 'feedreader'

MAX_ENTRIES = 20

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {
        vol.Required(CONF_URLS): vol.All(cv.ensure_list, [cv.url]),
    }
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Feedreader component."""
    urls = config.get(DOMAIN)[CONF_URLS]
    data_file = hass.config.path("{}.pickle".format(DOMAIN))
    storage = StoredData(data_file)
    feeds = [FeedManager(url, hass, storage) for url in urls]
    return len(feeds) > 0


class FeedManager(object):
    """Abstraction over Feedparser module."""

    def __init__(self, url, hass, storage):
        """Initialize the FeedManager object, poll every hour."""
        self._url = url
        self._feed = None
        self._hass = hass
        self._firstrun = True
        self._storage = storage
        self._last_entry_timestamp = None
        self._has_published_parsed = False
        hass.bus.listen_once(
            EVENT_HOMEASSISTANT_START, lambda _: self._update())
        track_utc_time_change(
            hass, lambda now: self._update(), minute=0, second=0)

    def _log_no_entries(self):
        """Send no entries log at debug level."""
        _LOGGER.debug("No new entries to be published in feed %s", self._url)

    def _update(self):
        """Update the feed and publish new entries to the event bus."""
        import feedparser
        _LOGGER.info("Fetching new data from feed %s", self._url)
        self._feed = feedparser.parse(self._url,
                                      etag=None if not self._feed
                                      else self._feed.get('etag'),
                                      modified=None if not self._feed
                                      else self._feed.get('modified'))
        if not self._feed:
            _LOGGER.error("Error fetching feed data from %s", self._url)
        else:
            if self._feed.bozo != 0:
                _LOGGER.error("Error parsing feed %s", self._url)
            # Using etag and modified, if there's no new data available,
            # the entries list will be empty
            elif self._feed.entries:
                _LOGGER.debug("%s entri(es) available in feed %s",
                              len(self._feed.entries), self._url)
                if len(self._feed.entries) > MAX_ENTRIES:
                    _LOGGER.debug("Processing only the first %s entries "
                                  "in feed %s", MAX_ENTRIES, self._url)
                    self._feed.entries = self._feed.entries[0:MAX_ENTRIES]
                self._publish_new_entries()
                if self._has_published_parsed:
                    self._storage.put_timestamp(
                        self._url, self._last_entry_timestamp)
            else:
                self._log_no_entries()
        _LOGGER.info("Fetch from feed %s completed", self._url)

    def _update_and_fire_entry(self, entry):
        """Update last_entry_timestamp and fire entry."""
        # We are lucky, `published_parsed` data available, let's make use of
        # it to publish only new available entries since the last run
        if 'published_parsed' in entry.keys():
            self._has_published_parsed = True
            self._last_entry_timestamp = max(
                entry.published_parsed, self._last_entry_timestamp)
        else:
            self._has_published_parsed = False
            _LOGGER.debug("No published_parsed info available for entry %s",
                          entry.title)
        entry.update({'feed_url': self._url})
        self._hass.bus.fire(EVENT_FEEDREADER, entry)

    def _publish_new_entries(self):
        """Publish new entries to the event bus."""
        new_entries = False
        self._last_entry_timestamp = self._storage.get_timestamp(self._url)
        if self._last_entry_timestamp:
            self._firstrun = False
        else:
            # Set last entry timestamp as epoch time if not available
            self._last_entry_timestamp = \
                datetime.utcfromtimestamp(0).timetuple()
        for entry in self._feed.entries:
            if self._firstrun or (
                    'published_parsed' in entry.keys() and
                    entry.published_parsed > self._last_entry_timestamp):
                self._update_and_fire_entry(entry)
                new_entries = True
            else:
                _LOGGER.debug("Entry %s already processed", entry.title)
        if not new_entries:
            self._log_no_entries()
        self._firstrun = False


class StoredData(object):
    """Abstraction over pickle data storage."""

    def __init__(self, data_file):
        """Initialize pickle data storage."""
        self._data_file = data_file
        self._lock = Lock()
        self._cache_outdated = True
        self._data = {}
        self._fetch_data()

    def _fetch_data(self):
        """Fetch data stored into pickle file."""
        if self._cache_outdated and exists(self._data_file):
            try:
                _LOGGER.debug("Fetching data from file %s", self._data_file)
                with self._lock, open(self._data_file, 'rb') as myfile:
                    self._data = pickle.load(myfile) or {}
                    self._cache_outdated = False
            # pylint: disable=bare-except
            except:
                _LOGGER.error("Error loading data from pickled file %s",
                              self._data_file)

    def get_timestamp(self, url):
        """Return stored timestamp for given url."""
        self._fetch_data()
        return self._data.get(url)

    def put_timestamp(self, url, timestamp):
        """Update timestamp for given URL."""
        self._fetch_data()
        with self._lock, open(self._data_file, 'wb') as myfile:
            self._data.update({url: timestamp})
            _LOGGER.debug("Overwriting feed %s timestamp in storage file %s",
                          url, self._data_file)
            try:
                pickle.dump(self._data, myfile)
            # pylint: disable=bare-except
            except:
                _LOGGER.error(
                    "Error saving pickled data to %s", self._data_file)
        self._cache_outdated = True
