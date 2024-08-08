"""The NMBS integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "nmbs"

PLATFORMS: Final = [Platform.SENSOR]

CONF_STATION_FROM = "station_from"
CONF_STATION_TO = "station_to"
CONF_STATION_LIVE = "station_live"
CONF_EXCLUDE_VIAS = "exclude_vias"
CONF_SHOW_ON_MAP = "show_on_map"
