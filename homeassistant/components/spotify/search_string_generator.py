"""blah blah."""


class WeatherPlaylistMapper:
    """test."""

    # Dictionary storing the various combinations of weather conditions and temperatures with
    # corresponding category of playlists.
    spotify_category_mapping = {
        "sunny": {"warm": "summer", "cold": "Romance"},
        "rainy": {"warm": "Jazz", "cold": "Instrumental"},
    }

    # FIX: Is this correct?
    def __init__(self) -> None:
        """Initialize."""
        self.spotify_category_mapping = WeatherPlaylistMapper.spotify_category_mapping

    @staticmethod
    def map_weather_to_playlists(temperature, condition):
        """Test."""
        # Normalize the condition to lower case for reliable matching
        condition.lower()

        # Classification of if given temperature is more so warm or cold
        # FIX: Need to consider the unit, F or C, and handle it. Now it's based on celsius.
        if temperature < 5:
            temperature_category = "cold"
        else:
            temperature_category = "warm"

        # Retrieval of the suitable spotify category.
        # FIX: Do we need to do error handling here? If the condition/temperature is not accurate?
        spotify_category = WeatherPlaylistMapper.spotify_category_mapping.get(
            condition
        ).get(temperature_category)

        # FIX: Check what exactly is expected to be returned
        return spotify_category

        # OLD CODE
        # Select a category based on weather condition
        # rainy, sunny, cloudy, windy, snowy
        # chill, summer, party, Netflix, Instrumental, Folk & Acoustic, pop, Romance, Jazz

        # if condition_key == "rainy" and temperature > 30:
        #     ret = "Rainy Day"
        # elif condition_key == "rainy" and temperature > 0:
        #     ret = "Summer Hits"
        # elif condition_key == "rainy" and temperature < 0:
        #     ret = "Winter Chill"
        # elif condition_key == "rainy" and temperature < 0:
        #     ret = "Winter Chill"
        # else:
        #     ret = "Daily Mix"

        # return ret
