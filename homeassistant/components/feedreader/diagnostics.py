"""Diagnostics support for Feedreader."""

from calendar import timegm
from time import struct_time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .coordinator import FeedReaderConfigEntry


def _isoformat(timestamp: struct_time | None) -> str | None:
    """Convert a UTC struct_time to an ISO 8601 string."""
    if timestamp is None:
        return None
    return dt_util.utc_from_timestamp(timegm(timestamp)).isoformat()


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FeedReaderConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    feed = coordinator.feed

    # The feed URL, title, author, and entries are left out, as they can
    # identify the user or be private.
    feed_info: dict[str, Any] | None = None
    if feed is not None:
        feed_meta = feed.get("feed", {})
        bozo_exception = feed.get("bozo_exception")
        feed_info = {
            "version": coordinator.feed_version,
            "http_status": feed.get("status"),
            "bozo": bool(feed.get("bozo")),
            "bozo_exception": (
                type(bozo_exception).__name__ if bozo_exception else None
            ),
            "entry_count": len(feed.get("entries", [])),
            "updated": _isoformat(
                feed_meta.get("updated_parsed") or feed_meta.get("published_parsed")
            ),
        }

    return {
        "config_entry": {
            "max_entries": coordinator.max_entries,
        },
        "feed": feed_info,
        "last_entry_timestamp": _isoformat(coordinator.last_entry_timestamp),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": (
                type(coordinator.last_exception).__name__
                if coordinator.last_exception
                else None
            ),
            "new_entries": (
                len(data) if (data := coordinator.data_or_none) is not None else None
            ),
        },
    }
