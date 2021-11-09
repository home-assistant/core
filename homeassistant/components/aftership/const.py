"""Constants for the Aftership integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

DOMAIN: Final = "aftership"

ATTRIBUTION: Final = "Information provided by AfterShip"
ATTR_TRACKINGS: Final = "trackings"

BASE: Final = "https://track.aftership.com/"

CONF_SLUG: Final = "slug"
CONF_TITLE: Final = "title"
CONF_TRACKING_NUMBER: Final = "tracking_number"

DEFAULT_NAME: Final = "aftership"
UPDATE_TOPIC: Final = f"{DOMAIN}_update"

ICON: Final = "mdi:package-variant-closed"

MIN_TIME_BETWEEN_UPDATES: Final = timedelta(minutes=15)

SERVICE_ADD_TRACKING: Final = "add_tracking"
SERVICE_REMOVE_TRACKING: Final = "remove_tracking"

ADD_TRACKING_SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_TRACKING_NUMBER): cv.string,
        vol.Optional(CONF_TITLE): cv.string,
        vol.Optional(CONF_SLUG): cv.string,
    }
)

REMOVE_TRACKING_SERVICE_SCHEMA: Final = vol.Schema(
    {vol.Required(CONF_SLUG): cv.string, vol.Required(CONF_TRACKING_NUMBER): cv.string}
)
