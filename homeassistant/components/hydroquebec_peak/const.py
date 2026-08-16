"""Constants for the Hydro-Québec Peak Events integration."""

from datetime import timedelta
import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "hydroquebec_peak"
LOGGER = logging.getLogger(__package__)

CONF_OFFER: Final = "offer"

# The feed is a small static file behind a CDN and events are published
# hours in advance; conditional requests make polling cheap.
SCAN_INTERVAL: Final = timedelta(minutes=15)

PLATFORMS: Final = [Platform.SENSOR]

EVENTS_TABLE_URL: Final = (
    "https://donnees.hydroquebec.com/explore/dataset/evenements-pointe/table/"
    "?sort=datedebut"
)
