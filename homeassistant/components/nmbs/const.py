"""The NMBS integration."""

from typing import Final

from pyrail import iRail

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "nmbs"

PLATFORMS: Final = [Platform.SENSOR]

CONF_STATION_FROM = "station_from"
CONF_STATION_TO = "station_to"
CONF_STATION_LIVE = "station_live"
CONF_EXCLUDE_VIAS = "exclude_vias"
CONF_SHOW_ON_MAP = "show_on_map"


class NMBSGlobalData:
    """Global data storage for NMBS."""

    stations: list[dict[str, str]] = []

    # only filled up during import from configuration.yaml
    localized_names: dict[str, str] = {}


NMBS_KEY: HassKey[NMBSGlobalData] = HassKey(DOMAIN)


async def gather_localized_station_names(hass: HomeAssistant):
    """Fetch the station names in all 4 languages."""

    localized_importable_names = {}
    languages = ["nl", "fr", "en", "de"]
    for lang in languages:
        api_client = iRail(lang=lang)
        station_response = await hass.async_add_executor_job(api_client.get_stations)
        if station_response == -1:
            return None
        for station in station_response["station"]:
            if station["name"] not in localized_importable_names:
                localized_importable_names[station["name"]] = station["standardname"]
    return localized_importable_names


def find_station_by_name(
    hass: HomeAssistant, station_name: str, localized_importable_names: dict
):
    """Find given station_name in the station list."""
    # Check if the station_name is a localized name and get the standard name
    standard_name = localized_importable_names.get(station_name, station_name)

    return next(
        (s for s in hass.data[NMBS_KEY].stations if standard_name == s["standardname"]),
        None,
    )


def find_station(hass: HomeAssistant, station_name: str):
    """Find given station_id in the station list."""
    return next(
        (s for s in hass.data[NMBS_KEY].stations if station_name in s["id"]),
        None,
    )
