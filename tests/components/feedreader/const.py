"""Constants for the tests for the feedreader component."""

from homeassistant.components.feedreader.const import (
    CONF_MAX_ENTRIES,
    DEFAULT_MAX_ENTRIES,
)
from homeassistant.const import APPLICATION_NAME, CONF_URL, __version__ as ha_version

URL = "http://some.rss.local/rss_feed.xml"
USER_AGENT = f"{APPLICATION_NAME}/{ha_version}"
FEED_TITLE = "RSS Sample"
VALID_CONFIG_DEFAULT = {CONF_URL: URL, CONF_MAX_ENTRIES: DEFAULT_MAX_ENTRIES}
VALID_CONFIG_100 = {CONF_URL: URL, CONF_MAX_ENTRIES: 100}
VALID_CONFIG_5 = {CONF_URL: URL, CONF_MAX_ENTRIES: 5}
VALID_CONFIG_1 = {CONF_URL: URL, CONF_MAX_ENTRIES: 1}
