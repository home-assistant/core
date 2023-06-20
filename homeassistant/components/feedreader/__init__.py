"""Support for RSS/Atom feeds."""
from __future__ import annotations

from datetime import datetime, timedelta
from logging import getLogger
from os.path import exists
import pickle
from threading import Lock
from time import struct_time
from typing import cast

import feedparser
import voluptuous as vol

from homeassistant.const import CONF_SCAN_INTERVAL, EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.typing import ConfigType

_LOGGER = getLogger(__name__)

CONF_URLS = "urls"
CONF_MAX_ENTRIES = "max_entries"

DEFAULT_MAX_ENTRIES = 20
DEFAULT_SCAN_INTERVAL = timedelta(hours=1)

DOMAIN = "feedreader"

EVENT_FEEDREADER = "feedreader"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Required(CONF_URLS): vol.All(cv.ensure_list, [cv.url]),
            vol.Optional(
                CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
            ): cv.time_period,
            vol.Optional(
                CONF_MAX_ENTRIES, default=DEFAULT_MAX_ENTRIES
            ): cv.positive_int,
        }
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Feedreader component."""
    urls: list[str] = config[DOMAIN][CONF_URLS]
    scan_interval: timedelta = config[DOMAIN][CONF_SCAN_INTERVAL]
    max_entries: int = config[DOMAIN][CONF_MAX_ENTRIES]
    data_file = hass.config.path(f"{DOMAIN}.pickle")
    storage = StoredData(data_file)
    feeds = [
        FeedManager(url, scan_interval, max_entries, hass, storage) for url in urls
    ]
    return len(feeds) > 0


class FeedManager:
    """Abstraction over Feedparser module."""

    def __init__(
        self,
        url: str,
        scan_interval: timedelta,
        max_entries: int,
        hass: HomeAssistant,
        storage: StoredData,
    ) -> None:
        """Initialize the FeedManager object, poll as per scan interval."""
        self._url = url
        self._scan_interval = scan_interval
        self._max_entries = max_entries
        self._feed: feedparser.FeedParserDict | None = None
        self._hass = hass
        self._firstrun = True
        self._storage = storage
        self._last_entry_timestamp: struct_time | None = None
        self._last_update_successful = False
        self._has_published_parsed = False
        self._has_updated_parsed = False
        self._event_type = EVENT_FEEDREADER
        self._feed_id = url
        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, lambda _: self._update())
        self._init_regular_updates(hass)

    def _log_no_entries(self) -> None:
        """Send no entries log at debug level."""
        _LOGGER.debug("No new entries to be published in feed %s", self._url)

    def _init_regular_updates(self, hass: HomeAssistant) -> None:
        """Schedule regular updates at the top of the clock."""
        track_time_interval(
            hass,
            lambda now: self._update(),
            self._scan_interval,
            cancel_on_shutdown=True,
        )

    @property
    def last_update_successful(self) -> bool:
        """Return True if the last feed update was successful."""
        return self._last_update_successful

    def _update(self) -> None:
        """Update the feed and publish new entries to the event bus."""
        _LOGGER.info("Fetching new data from feed %s", self._url)
        self._feed: feedparser.FeedParserDict = feedparser.parse(  # type: ignore[no-redef]
            self._url,
            etag=None if not self._feed else self._feed.get("etag"),
            modified=None if not self._feed else self._feed.get("modified"),
        )
        if not self._feed:
            _LOGGER.error("Error fetching feed data from %s", self._url)
            self._last_update_successful = False
        else:
            # The 'bozo' flag really only indicates that there was an issue
            # during the initial parsing of the XML, but it doesn't indicate
            # whether this is an unrecoverable error. In this case the
            # feedparser lib is trying a less strict parsing approach.
            # If an error is detected here, log warning message but continue
            # processing the feed entries if present.
            if self._feed.bozo != 0:
                _LOGGER.warning(
                    "Possible issue parsing feed %s: %s",
                    self._url,
                    self._feed.bozo_exception,
                )
            # Using etag and modified, if there's no new data available,
            # the entries list will be empty
            if self._feed.entries:
                _LOGGER.debug(
                    "%s entri(es) available in feed %s",
                    len(self._feed.entries),
                    self._url,
                )
                self._filter_entries()
                self._publish_new_entries()
                if self._has_published_parsed or self._has_updated_parsed:
                    self._storage.put_timestamp(
                        self._feed_id, cast(struct_time, self._last_entry_timestamp)
                    )
            else:
                self._log_no_entries()
            self._last_update_successful = True
        _LOGGER.info("Fetch from feed %s completed", self._url)

    def _filter_entries(self) -> None:
        """Filter the entries provided and return the ones to keep."""
        assert self._feed is not None
        if len(self._feed.entries) > self._max_entries:
            _LOGGER.debug(
                "Processing only the first %s entries in feed %s",
                self._max_entries,
                self._url,
            )
            self._feed.entries = self._feed.entries[0 : self._max_entries]

    def _update_and_fire_entry(self, entry: feedparser.FeedParserDict) -> None:
        """Update last_entry_timestamp and fire entry."""
        # Check if the entry has a updated or published date.
        # Start from a updated date because generally `updated` > `published`.
        if "updated_parsed" in entry and entry.updated_parsed:
            # We are lucky, `updated_parsed` data available, let's make use of
            # it to publish only new available entries since the last run
            self._has_updated_parsed = True
            self._last_entry_timestamp = max(
                entry.updated_parsed, self._last_entry_timestamp
            )
        elif "published_parsed" in entry and entry.published_parsed:
            # We are lucky, `published_parsed` data available, let's make use of
            # it to publish only new available entries since the last run
            self._has_published_parsed = True
            self._last_entry_timestamp = max(
                entry.published_parsed, self._last_entry_timestamp
            )
        else:
            self._has_updated_parsed = False
            self._has_published_parsed = False
            _LOGGER.debug(
                "No updated_parsed or published_parsed info available for entry %s",
                entry,
            )
        entry.update({"feed_url": self._url})
        self._hass.bus.fire(self._event_type, entry)

    def _publish_new_entries(self) -> None:
        """Publish new entries to the event bus."""
        assert self._feed is not None
        new_entries = False
        self._last_entry_timestamp = self._storage.get_timestamp(self._feed_id)
        if self._last_entry_timestamp:
            self._firstrun = False
        else:
            # Set last entry timestamp as epoch time if not available
            self._last_entry_timestamp = datetime.utcfromtimestamp(0).timetuple()
        for entry in self._feed.entries:
            if (
                self._firstrun
                or (
                    "published_parsed" in entry
                    and entry.published_parsed > self._last_entry_timestamp
                )
                or (
                    "updated_parsed" in entry
                    and entry.updated_parsed > self._last_entry_timestamp
                )
            ):
                self._update_and_fire_entry(entry)
                new_entries = True
            else:
                _LOGGER.debug("Entry %s already processed", entry)
        if not new_entries:
            self._log_no_entries()
        self._firstrun = False


class StoredData:
    """Abstraction over pickle data storage."""

    def __init__(self, data_file: str) -> None:
        """Initialize pickle data storage."""
        self._data_file = data_file
        self._lock = Lock()
        self._cache_outdated = True
        self._data: dict[str, struct_time] = {}
        self._fetch_data()

    def _fetch_data(self) -> None:
        """Fetch data stored into pickle file."""
        if self._cache_outdated and exists(self._data_file):
            try:
                _LOGGER.debug("Fetching data from file %s", self._data_file)
                with self._lock, open(self._data_file, "rb") as myfile:
                    self._data = pickle.load(myfile) or {}
                    self._cache_outdated = False
            except Exception:  # pylint: disable=broad-except
                _LOGGER.error(
                    "Error loading data from pickled file %s", self._data_file
                )

    def get_timestamp(self, feed_id: str) -> struct_time | None:
        """Return stored timestamp for given feed id (usually the url)."""
        self._fetch_data()
        return self._data.get(feed_id)

    def put_timestamp(self, feed_id: str, timestamp: struct_time) -> None:
        """Update timestamp for given feed id (usually the url)."""
        self._fetch_data()
        with self._lock, open(self._data_file, "wb") as myfile:
            self._data.update({feed_id: timestamp})
            _LOGGER.debug(
                "Overwriting feed %s timestamp in storage file %s: %s",
                feed_id,
                self._data_file,
                timestamp,
            )
            try:
                pickle.dump(self._data, myfile)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.error("Error saving pickled data to %s", self._data_file)
        self._cache_outdated = True
