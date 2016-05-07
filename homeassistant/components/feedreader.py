"""
Support for RSS/Atom feed.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/feedreader/
"""
from datetime import datetime
from logging import getLogger
import voluptuous as vol
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.helpers.event import track_utc_time_change

REQUIREMENTS = ['feedparser==5.2.1']
_LOGGER = getLogger(__name__)
DOMAIN = "feedreader"
EVENT_FEEDREADER = "feedreader"
# pylint: disable=no-value-for-parameter
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {
        'urls': [vol.Url()],
    }
}, extra=vol.ALLOW_EXTRA)
MAX_ENTRIES = 20


# pylint: disable=too-few-public-methods
class FeedManager(object):
    """Abstraction over feedparser module."""

    def __init__(self, url, hass):
        """Initialize the FeedManager object, poll every hour."""
        self._url = url
        self._feed = None
        self._hass = hass
        self._firstrun = True
        # Initialize last entry timestamp as epoch time
        self._last_entry_timestamp = datetime.utcfromtimestamp(0).timetuple()
        hass.bus.listen_once(EVENT_HOMEASSISTANT_START,
                             lambda _: self._update())
        track_utc_time_change(hass, lambda now: self._update(),
                              minute=0, second=0)

    def _log_no_entries(self):
        """Send no entries log at debug level."""
        _LOGGER.debug('No new entries in feed "%s"', self._url)

    def _update(self):
        """Update the feed and publish new entries to the event bus."""
        import feedparser
        _LOGGER.info('Fetching new data from feed "%s"', self._url)
        self._feed = feedparser.parse(self._url,
                                      etag=None if not self._feed
                                      else self._feed.get('etag'),
                                      modified=None if not self._feed
                                      else self._feed.get('modified'))
        if not self._feed:
            _LOGGER.error('Error fetching feed data from "%s"', self._url)
        else:
            if self._feed.bozo != 0:
                _LOGGER.error('Error parsing feed "%s"', self._url)
            # Using etag and modified, if there's no new data available,
            # the entries list will be empty
            elif len(self._feed.entries) > 0:
                _LOGGER.debug('%s entri(es) available in feed "%s"',
                              len(self._feed.entries),
                              self._url)
                if len(self._feed.entries) > MAX_ENTRIES:
                    _LOGGER.debug('Publishing only the first %s entries '
                                  'in feed "%s"', MAX_ENTRIES, self._url)
                    self._feed.entries = self._feed.entries[0:MAX_ENTRIES]
                self._publish_new_entries()
            else:
                self._log_no_entries()
        _LOGGER.info('Fetch from feed "%s" completed', self._url)

    def _update_and_fire_entry(self, entry):
        """Update last_entry_timestamp and fire entry."""
        # We are lucky, `published_parsed` data available,
        # let's make use of it to publish only new available
        # entries since the last run
        if 'published_parsed' in entry.keys():
            self._last_entry_timestamp = max(entry.published_parsed,
                                             self._last_entry_timestamp)
        else:
            _LOGGER.debug('No `published_parsed` info available '
                          'for entry "%s"', entry.title)
        entry.update({'feed_url': self._url})
        self._hass.bus.fire(EVENT_FEEDREADER, entry)

    def _publish_new_entries(self):
        """Publish new entries to the event bus."""
        new_entries = False
        for entry in self._feed.entries:
            if self._firstrun or (
                    'published_parsed' in entry.keys() and
                    entry.published_parsed > self._last_entry_timestamp):
                self._update_and_fire_entry(entry)
                new_entries = True
            else:
                _LOGGER.debug('Entry "%s" already processed', entry.title)
        if not new_entries:
            self._log_no_entries()
        self._firstrun = False


def setup(hass, config):
    """Setup the feedreader component."""
    urls = config.get(DOMAIN)['urls']
    feeds = [FeedManager(url, hass) for url in urls]
    return len(feeds) > 0
