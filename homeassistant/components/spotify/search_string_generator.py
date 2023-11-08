"""blah blah."""


class WeatherPlaylistMapper:
    """test."""

    @staticmethod
    def map_weather_to_playlist(temperature, condition):
        """Test."""
        # Normalize the condition to lower case for reliable matching
        condition_key = condition.lower()

        # Select a category based on weather condition
        # rainy, sunny, cloudy, windy, snowy
        # chill, summer, party, Netflix, Instrumental, Folk & Acoustic, pop, Romance, Jazz
        if condition_key == "rainy" and temperature > 30:
            ret = "Rainy Day"
        elif condition_key == "rainy" and temperature > 0:
            ret = "Summer Hits"
        elif condition_key == "rainy" and temperature < 0:
            ret = "Winter Chill"
        elif condition_key == "rainy" and temperature < 0:
            ret = "Winter Chill"
        else:
            ret = "Daily Mix"

        return ret
