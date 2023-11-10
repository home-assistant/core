"""Contains the WeatherPlaylistMapper class, which provides functionality to map weather conditions and temperature ranges to corresponding Spotify playlist IDs."""

import json


class WeatherPlaylistMapper:
    """A class to map weather conditions and temperatures to Spotify playlist categories."""

    # Constant for the temperature threshold
    TEMPERATURE_THRESHOLD_CELSIUS = 15

    def __init__(self, mapping_file="spotify_mappings.json") -> None:
        """Initialize the WeatherPlaylistMapper with mappings from a file.

        Args:
            mapping_file (str): The path to the JSON file containing playlist mappings.

        Raises:
            FileNotFoundError: If the mapping file is not found.
        """
        try:
            with open(mapping_file, encoding="utf-8") as file:
                self.spotify_category_mapping = json.load(file)
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"The mapping file {mapping_file} was not found."
            ) from e

    def map_weather_to_playlists(self, temperature: float, condition: str) -> str:
        """Map the given weather condition and temperature to a Spotify playlist category ID.

        Args:
            temperature (float): The current temperature.
            condition (str): The current weather condition.

        Returns:
            str: The Spotify playlist ID corresponding to the given weather condition
                 and temperature.

        Raises:
            ValueError: If the condition is not recognized or no mapping exists for the
                        given temperature category.
        """

        # Normalize the condition to lower case for reliable matching
        condition = condition.strip().lower()

        # Determine if the temperature is warm or cold
        # FIX: Consider the unit of temperature (Fahrenheit or Celsius) and handle accordingly.
        temperature_category = (
            "cold" if temperature < self.TEMPERATURE_THRESHOLD_CELSIUS else "warm"
        )

        # Retrieve the suitable Spotify category ID from the mapping
        # Handle cases where the condition is not in the mapping
        # FIX: Handle the ValueError in the code that calls this method,
        condition_mapping = self.spotify_category_mapping.get(condition)
        if not condition_mapping:
            raise ValueError(f"Weather condition {condition} does not exist")

        spotify_search_string = condition_mapping.get(temperature_category)
        if not spotify_search_string:
            raise ValueError(
                f"No playlist search string mapping for temperature category: {temperature_category}"
            )

        return spotify_search_string
