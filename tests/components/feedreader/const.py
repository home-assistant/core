"""Constants for the tests for the feedreader component."""

from homeassistant.components.feedreader.const import (
    CONF_MAX_ENTRIES,
    DEFAULT_MAX_ENTRIES,
)
from homeassistant.const import CONF_URL

URL = "http://some.rss.local/rss_feed.xml"
FEED_TITLE = "RSS Sample"
VALID_CONFIG_DEFAULT = {CONF_URL: URL, CONF_MAX_ENTRIES: DEFAULT_MAX_ENTRIES}
VALID_CONFIG_100 = {CONF_URL: URL, CONF_MAX_ENTRIES: 100}
VALID_CONFIG_5 = {CONF_URL: URL, CONF_MAX_ENTRIES: 5}
VALID_CONFIG_1 = {CONF_URL: URL, CONF_MAX_ENTRIES: 1}
