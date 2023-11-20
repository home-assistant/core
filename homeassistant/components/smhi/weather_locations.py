"""Weather Locations."""

import json
from typing import Any

from .downloader import SmhiDownloader
from .smhi_geolocation_event import SmhiGeolocationEvent


class SmhiWeatherLocations:
    """Smhi Weather Locations."""

    # sweden_corner_locations = [
    #     {"name": "NW CORNER", "latitude": 69.05, "longitude": 10.59},
    #     {"name": "NE CORNER", "latitude": 69.05, "longitude": 24.17},
    #     {"name": "SW CORNER", "latitude": 55.13, "longitude": 10.59},
    #     {"name": "SE CORNER", "latitude": 55.13, "longitude": 24.17}
    # ]

    celsius_symbol = chr(176) + "C"

    def get_cities(self) -> list:
        """Get the cities which will be used as weather locations."""
        # Open the JSON file for reading
        with open(
            "homeassistant/components/smhi/notable_cities.json", encoding="utf-8"
        ) as file:
            # Load the JSON data from the file
            data = json.load(file)

        cities = []
        for city in data["cities"]:
            parsed_city = {
                "name": city.get("city"),
                "latitude": float(city.get("lat")),
                "longitude": float(city.get("lng")),
            }
            cities.append(parsed_city)

        return cities

    async def get_weather_data(self, lat: float, lon: float) -> Any:
        """Get weather data from SMHI api."""
        weather_api_url = f"https://opendata-download-metfcst.smhi.se/api/category/pmp3g/version/2/geotype/point/lon/{lon}/lat/{lat}/data.json"

        smhi_downloader = SmhiDownloader()
        data = await smhi_downloader.download_json(weather_api_url)

        return data

    async def get_weather_locations(self) -> list[SmhiGeolocationEvent]:
        """Get the weather location entities."""
        weather_location_entities = []
        for city in self.get_cities():
            city_weather_data = await self.get_weather_data(
                city["latitude"], city["longitude"]
            )
            timeseries_data = city_weather_data.get("timeSeries")[0]
            temperature_data = timeseries_data.get("parameters")[10]
            temperature_text = (
                str(temperature_data["values"][0]) + " " + self.celsius_symbol
            )

            geolocation_event = SmhiGeolocationEvent(
                city["name"] + " - Temperature: " + temperature_text,
                city["latitude"],
                city["longitude"],
            )
            weather_location_entities.append(geolocation_event)

        return weather_location_entities
