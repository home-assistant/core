"""Weather Locations."""

import json
from typing import Any

from .const import weather_conditions, weather_icons
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

            # TEMPERATURE
            temperature = self.get_parameter_value(timeseries_data, "t")
            temperature_text = str(temperature) + " " + self.celsius_symbol

            # WEATHER CONDITION
            weather_condition_index = self.get_parameter_value(
                timeseries_data, "Wsymb2"
            )
            condition_icon = self.get_weather_condition_icon(weather_condition_index)
            icon_url = weather_icons[condition_icon]
            condition_name = weather_conditions[str(weather_condition_index)]

            geolocation_event = SmhiGeolocationEvent(
                city["name"]
                + " - Temperature: "
                + temperature_text
                + ", "
                + condition_name,
                city["latitude"],
                city["longitude"],
                icon_url,
                "mdi:cloud-outline",
                "stationary",
            )
            weather_location_entities.append(geolocation_event)

        return weather_location_entities

    def get_parameter_value(self, timeseries_data: Any, parameter_name: str) -> int:
        """Get the value from a parameter in the timeSeries data."""
        parameters = timeseries_data.get("parameters")
        for data in parameters:
            if data["name"] == parameter_name:
                return int(data["values"][0])

        raise ValueError("Value not found in the data.")

    def get_weather_condition_icon(self, weather_condition_index: int) -> str:
        """Get the weather condition icon."""
        # Value | Meaning
        # 1	      Clear sky
        # 2	      Nearly clear sky
        # 3	      Variable cloudiness
        # 4	      Halfclear sky
        # 5	      Cloudy sky
        # 6	      Overcast
        # 7	      Fog
        # 8	      Light rain showers
        # 9	      Moderate rain showers
        # 10	  Heavy rain showers
        # 11	  Thunderstorm
        # 12	  Light sleet showers
        # 13	  Moderate sleet showers
        # 14	  Heavy sleet showers
        # 15	  Light snow showers
        # 16	  Moderate snow showers
        # 17	  Heavy snow showers
        # 18	  Light rain
        # 19	  Moderate rain
        # 20	  Heavy rain
        # 21	  Thunder
        # 22	  Light sleet
        # 23	  Moderate sleet
        # 24	  Heavy sleet
        # 25	  Light snowfall
        # 26	  Moderate snowfall
        # 27	  Heavy snowfall

        # Clear sky
        if weather_condition_index in (1, 2, 3):
            return "SUN"
        # Clouds
        if weather_condition_index in (4, 5, 6, 7):
            return "CLOUD"
        # Rain
        if weather_condition_index in (8, 9, 10, 11, 18, 19, 20, 21):
            return "RAIN"
        # Snow
        if weather_condition_index in (
            12,
            13,
            14,
            15,
            16,
            17,
            22,
            23,
            24,
            25,
            26,
            27,
        ):
            return "SNOWFLAKE"

        return "NULL"
