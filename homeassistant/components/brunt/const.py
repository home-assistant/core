"""Constants for Brunt."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "brunt"
ATTR_REQUEST_POSITION = "request_position"
NOTIFICATION_ID = "brunt_notification"
NOTIFICATION_TITLE = "Brunt Cover Setup"
ATTRIBUTION = "Based on an unofficial Brunt SDK."
PLATFORMS = [Platform.COVER]

CLOSED_POSITION = 0
OPEN_POSITION = 100

REGULAR_INTERVAL = timedelta(seconds=20)
FAST_INTERVAL = timedelta(seconds=5)
