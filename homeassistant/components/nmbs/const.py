"""The NMBS integration."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from pyrail.models import StationDetails

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "nmbs"
STATION_CACHE_DURATION = timedelta(days=1)


@dataclass
class NMBSStationCache:
    """Cached station data shared by NMBS config entries."""

    stations: list[StationDetails]
    fetched_at: datetime


NMBS_STATION_DATA: HassKey[NMBSStationCache] = HassKey(DOMAIN)

PLATFORMS: Final = [Platform.SENSOR]

LIVEBOARD_UNIQUE_ID_PREFIX: Final = "nmbs_live_"
CONNECTION_UNIQUE_ID_PREFIX: Final = "nmbs_connection_"
CONNECTION_FEED: Final = "connection"

CONF_STATION_FROM = "station_from"
CONF_STATION_TO = "station_to"
CONF_EXCLUDE_VIAS = "exclude_vias"
