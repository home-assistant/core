"""Data update coordinator for RSS/Atom feeds."""

from __future__ import annotations

from calendar import timegm
from datetime import datetime
from logging import getLogger
from time import gmtime, struct_time
from typing import TYPE_CHECKING
from urllib.error import URLError

import feedparser

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, EVENT_FEEDREADER

DELAY_SAVE = 30
STORAGE_VERSION = 1


_LOGGER = getLogger(__name__)


class FeedReaderCoordinator(
    DataUpdateCoordinator[list[feedparser.FeedParserDict] | None]
):
    """Abstraction over Feedparser module."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        url: str,
        max_entries: int,
        storage: StoredData,
    ) -> None:
        """Initialize the FeedManager object, poll as per scan interval."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN} {url}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.url = url
        self.feed_author: str | None = None
        self.feed_version: str | None = None
        self._max_entries = max_entries
        self._storage = storage
        self._last_entry_timestamp: struct_time | None = None
        self._event_type = EVENT_FEEDREADER
        self._feed: feedparser.FeedParserDict | None = None
        self._feed_id = url

    @callback
    def _log_no_entries(self) -> None:
        """Send no entries log at debug level."""
        _LOGGER.debug("No new entries to be published in feed %s", self.url)

    async def _async_fetch_feed(self) -> feedparser.FeedParserDict:
        """Fetch the feed data."""
        _LOGGER.debug("Fetching new data from feed %s", self.url)

        def _parse_feed() -> feedparser.FeedParserDict:
            return feedparser.parse(
                self.url,
                etag=None if not self._feed else self._feed.get("etag"),
                modified=None if not self._feed else self._feed.get("modified"),
            )

        feed = await self.hass.async_add_executor_job(_parse_feed)

        if not feed:
            raise UpdateFailed(f"Error fetching feed data from {self.url}")

        # The 'bozo' flag really only indicates that there was an issue
        # during the initial parsing of the XML, but it doesn't indicate
        # whether this is an unrecoverable error. In this case the
        # feedparser lib is trying a less strict parsing approach.
        # If an error is detected here, log warning message but continue
        # processing the feed entries if present.
        if feed.bozo != 0:
            if isinstance(feed.bozo_exception, URLError):
                raise UpdateFailed(
                    f"Error fetching feed data from {self.url} : {feed.bozo_exception}"
                )

            # no connection issue, but parsing issue
            _LOGGER.warning(
                "Possible issue parsing feed %s: %s",
                self.url,
                feed.bozo_exception,
            )
        return feed

    async def async_setup(self) -> None:
        """Set up the feed manager."""
        feed = await self._async_fetch_feed()
        self.logger.debug("Feed data fetched from %s : %s", self.url, feed["feed"])
        self.feed_author = feed["feed"].get("author")
        self.feed_version = feedparser.api.SUPPORTED_VERSIONS.get(feed["version"])
        self._feed = feed

    async def _async_update_data(self) -> list[feedparser.FeedParserDict] | None:
        """Update the feed and publish new entries to the event bus."""
        assert self._feed is not None
        # _last_entry_timestamp is not set during async_setup, but we have already
        # fetched data, so we can use them, instead of fetch again
        if self._last_entry_timestamp:
            self._feed = await self._async_fetch_feed()

        # Using etag and modified, if there's no new data available,
        # the entries list will be empty
        _LOGGER.debug(
            "%s entri(es) available in feed %s",
            len(self._feed.entries),
            self.url,
        )
        if not self._feed.entries:
            self._log_no_entries()
            return None

        if TYPE_CHECKING:
            assert isinstance(self._feed.entries, list)

        self._filter_entries()
        self._publish_new_entries()

        _LOGGER.debug("Fetch from feed %s completed", self.url)

        if self._last_entry_timestamp:
            self._storage.async_put_timestamp(self._feed_id, self._last_entry_timestamp)

        return self._feed.entries

    @callback
    def _filter_entries(self) -> None:
        """Filter the entries provided and return the ones to keep."""
        assert self._feed is not None
        if len(self._feed.entries) > self._max_entries:
            _LOGGER.debug(
                "Processing only the first %s entries in feed %s",
                self._max_entries,
                self.url,
            )
            self._feed.entries = self._feed.entries[0 : self._max_entries]

    @callback
    def _update_and_fire_entry(self, entry: feedparser.FeedParserDict) -> None:
        """Update last_entry_timestamp and fire entry."""
        # Check if the entry has a updated or published date.
        # Start from a updated date because generally `updated` > `published`.
        if time_stamp := entry.get("updated_parsed") or entry.get("published_parsed"):
            self._last_entry_timestamp = time_stamp
        else:
            _LOGGER.debug(
                "No updated_parsed or published_parsed info available for entry %s",
                entry,
            )
        entry["feed_url"] = self.url
        self.hass.bus.async_fire(self._event_type, entry)
        _LOGGER.debug("New event fired for entry %s", entry.get("link"))

    @callback
    def _publish_new_entries(self) -> None:
        """Publish new entries to the event bus."""
        assert self._feed is not None
        new_entry_count = 0
        firstrun = False
        self._last_entry_timestamp = self._storage.get_timestamp(self._feed_id)
        if not self._last_entry_timestamp:
            firstrun = True
            # Set last entry timestamp as epoch time if not available
            self._last_entry_timestamp = dt_util.utc_from_timestamp(0).timetuple()
        # locally cache self._last_entry_timestamp so that entries published at identical times can be processed
        last_entry_timestamp = self._last_entry_timestamp
        for entry in self._feed.entries:
            if firstrun or (
                (
                    time_stamp := entry.get("updated_parsed")
                    or entry.get("published_parsed")
                )
                and time_stamp > last_entry_timestamp
            ):
                self._update_and_fire_entry(entry)
                new_entry_count += 1
            else:
                _LOGGER.debug("Already processed entry %s", entry.get("link"))
        if new_entry_count == 0:
            self._log_no_entries()
        else:
            _LOGGER.debug("%d entries published in feed %s", new_entry_count, self.url)


class StoredData:
    """Represent a data storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize data storage."""
        self._data: dict[str, struct_time] = {}
        self.hass = hass
        self._store: Store[dict[str, str]] = Store(hass, STORAGE_VERSION, DOMAIN)
        self.is_initialized = False

    async def async_setup(self) -> None:
        """Set up storage."""
        if (store_data := await self._store.async_load()) is not None:
            # Make sure that dst is set to 0, by using gmtime() on the timestamp.
            self._data = {
                feed_id: gmtime(datetime.fromisoformat(timestamp_string).timestamp())
                for feed_id, timestamp_string in store_data.items()
            }
        self.is_initialized = True

    def get_timestamp(self, feed_id: str) -> struct_time | None:
        """Return stored timestamp for given feed id."""
        return self._data.get(feed_id)

    @callback
    def async_put_timestamp(self, feed_id: str, timestamp: struct_time) -> None:
        """Update timestamp for given feed id."""
        self._data[feed_id] = timestamp
        self._store.async_delay_save(self._async_save_data, DELAY_SAVE)

    @callback
    def _async_save_data(self) -> dict[str, str]:
        """Save feed data to storage."""
        return {
            feed_id: dt_util.utc_from_timestamp(timegm(struct_utc)).isoformat()
            for feed_id, struct_utc in self._data.items()
        }
