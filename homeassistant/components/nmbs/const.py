"""The NMBS integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "nmbs"

PLATFORMS: Final = [Platform.SENSOR]

LIVEBOARD_UNIQUE_ID_PREFIX: Final = "nmbs_live_"
CONNECTION_UNIQUE_ID_PREFIX: Final = "nmbs_connection_"
CONNECTION_FEED: Final = "connection"

CONF_STATION_FROM = "station_from"
CONF_STATION_TO = "station_to"
CONF_EXCLUDE_VIAS = "exclude_vias"
