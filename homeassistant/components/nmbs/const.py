"""The NMBS integration."""

from typing import Final

from pyrail.models import StationDetails

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "nmbs"
NMBS_STATION_DATA: HassKey[list[StationDetails]] = HassKey(DOMAIN)

PLATFORMS: Final = [Platform.SENSOR]

CONF_STATION_FROM = "station_from"
CONF_STATION_TO = "station_to"
CONF_EXCLUDE_VIAS = "exclude_vias"
