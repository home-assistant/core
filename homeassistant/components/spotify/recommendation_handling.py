from spotipy import Spotify  # noqa: D100

from homeassistant.core import HomeAssistant

BROWSE_LIMIT = 48


class RecommendationHandling:  # noqa: D101
    def handling_weather_recommendatios(  # noqa: D102
        self, hass: HomeAssistant, spotify: Spotify
    ):  # noqa: D102
        items = []
        weather_entity_id = "weather.home"
        weather_state = hass.states.get(weather_entity_id)

        if (
            weather_state is not None
            and "temperature" in weather_state.attributes
            and "forecast" in weather_state.attributes
        ):
            current_temperature = weather_state.attributes["temperature"]  # noqa: F841
            condition = weather_state.attributes["forecast"][0][  # noqa: F841
                "condition"
            ]  # noqa: F841
            # send current_temperature and condition to search_string_generator and get search string
            search_string = "cold rain"
            media = spotify.search(q=search_string, limit=BROWSE_LIMIT, type="playlist")
            items = media.get("playlists", {}).get("items", [])
        return items
