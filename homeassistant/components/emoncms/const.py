"""Constants for the emoncms integration."""

import logging

CONF_ONLY_INCLUDE_FEEDID = "include_only_feed_id"
CONF_MESSAGE = "message"
CONF_SUCCESS = "success"
DOMAIN = "emoncms"
EMONCMS_UUID_DOC_URL = (
    "https://docs.openenergymonitor.org/emoncms/update.html"
    "#upgrading-to-a-version-producing-a-unique-identifier"
)
FEED_ID = "id"
FEED_NAME = "name"
FEED_TAG = "tag"
SYNC_MODE = "sync_mode"
SYNC_MODE_AUTO = "auto"
SYNC_MODE_MANUAL = "manual"


LOGGER = logging.getLogger(__package__)
