"""Fetching fire risk data."""

from typing import Any, Optional

import aiohttp

from ..downloader import SmhiDownloader
from ..smhi_geolocation_event import SmhiGeolocationEvent

cities = {
    "Stockholm": {"lat": 59.3293, "lon": 18.0686},
    "Gothenburg": {"lat": 57.7089, "lon": 11.9746},
    "Malmö": {"lat": 55.6050, "lon": 13.0038},
    "Uppsala": {"lat": 59.8586, "lon": 17.6389},
    "Linköping": {"lat": 58.4109, "lon": 15.6214},
    "Västerås": {"lat": 59.6110, "lon": 16.5448},
    "Örebro": {"lat": 59.2753, "lon": 15.2134},
    "Norrköping": {"lat": 58.5942, "lon": 16.1826},
    "Helsingborg": {"lat": 56.0467, "lon": 12.6945},
    "Jönköping": {"lat": 57.7815, "lon": 14.1562},
    "Lund": {"lat": 55.7047, "lon": 13.1910},
    "Umeå": {"lat": 63.8258, "lon": 20.2630},
    "Gävle": {"lat": 60.6745, "lon": 17.1417},
    "Borås": {"lat": 57.7210, "lon": 12.9401},
    "Södertälje": {"lat": 59.1955, "lon": 17.6252},
    "Eskilstuna": {"lat": 59.3666, "lon": 16.5077},
    "Karlstad": {"lat": 59.4022, "lon": 13.5115},
    "Halmstad": {"lat": 56.6745, "lon": 12.8578},
    "Växjö": {"lat": 56.8777, "lon": 14.8091},
    "Sundsvall": {"lat": 62.3908, "lon": 17.3069},
}


def get_api_url_from_coordinates(lat: float, lon: float) -> str:
    """Get API url specific coordniates."""
    return f"https://opendata-download-metfcst.smhi.se/api/category/fwif1g/version/1/daily/geotype/point/lon/{lon}/lat/{lat}/data.json"


async def fetch_fire_risk_data(
    session: Optional[aiohttp.ClientSession] = None,
) -> list[dict[str, Any]]:
    """Fetch fire risk data using the provided aiohttp session or create a new one if not provided."""
    fire_risk_data: list[dict[str, Any]] = []
    downloader = SmhiDownloader()

    for __, city_coordinates in cities.items():
        url = get_api_url_from_coordinates(
            lat=city_coordinates["lat"], lon=city_coordinates["lon"]
        )
        if session:
            # If a session is provided, use it
            data = await downloader.fetch(session, url)
        else:
            # If no session is provided, use the downloader's own session creation method
            data = await downloader.download_json(url)
        if data:
            fire_risk_data.append(data)

    return fire_risk_data


def extract_grassfire_info_with_coords(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract grassfire data, combining entries with the same coordinates."""
    grassfire_risks_dict = {}

    coordinates = data.get("geometry", {}).get("coordinates", [[]])[0]

    for entry in data.get("timeSeries", []):
        valid_time = entry.get("validTime")
        grassfire_info = next(
            (
                param
                for param in entry.get("parameters", [])
                if param["name"] == "grassfire"
            ),
            None,
        )
        if grassfire_info:
            coord_key = tuple(coordinates)
            level_info = (
                str(grassfire_info.get("levelType", "")).capitalize()
                + ": "
                + str(grassfire_info.get("level", ""))
            )

            if coord_key not in grassfire_risks_dict:
                # If coordinates are new, create a new entry.
                grassfire_risks_dict[coord_key] = {
                    "validTime": valid_time,
                    "grassfireRisk": grassfire_info["values"][0],
                    "coordinates": coordinates,
                    "combinedLevelInfo": level_info,
                    "unit": grassfire_info.get("unit"),
                }
            else:
                # If coordinates already exist, combine the levelType and level information.
                existing_entry = grassfire_risks_dict[coord_key]
                existing_entry["combinedLevelInfo"] += " | " + level_info

    # Convert the dictionary back to a list before returning.
    return list(grassfire_risks_dict.values())


def create_smhi_geolocation_events(
    grassfire_risks: list[dict[str, Any]]
) -> list[SmhiGeolocationEvent]:
    """Convert a list of grassfire risk data to a list of SmhiGeolocationEvent objects."""
    events = []
    for risk in grassfire_risks:
        name = "Grassfire risk: " + risk["combinedLevelInfo"]
        event = SmhiGeolocationEvent(
            name=name,
            latitude=risk["coordinates"][1],
            longitude=risk["coordinates"][0],
            map_icon_url="https://opendata.smhi.se/apidocs/IBWwarnings/res/fire-outline-56x56@2x.png",
            card_icon="https://opendata.smhi.se/apidocs/IBWwarnings/res/fire-outline-56x56@2x.png",
            state=risk["combinedLevelInfo"],
            tag="fire_risk",
        )
        events.append(event)
    return events


async def get_grassfire_risk() -> list[SmhiGeolocationEvent]:
    """Get grassfire risk using the updated fetch_fire_risk_data function."""
    cleaned_data: list[dict[str, Any]] = []
    data = await fetch_fire_risk_data()
    for city_data in data:
        cleaned_data.extend(extract_grassfire_info_with_coords(city_data))
    return create_smhi_geolocation_events(cleaned_data)
