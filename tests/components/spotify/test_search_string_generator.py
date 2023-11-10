"""Module for testing the WeatherPlaylistMapper functionality in the Spotify integration."""

import json

import pytest

from homeassistant.components.spotify.search_string_generator import (
    WeatherPlaylistMapper,
)


# Fixture to load the test JSON data
@pytest.fixture
def spotify_mapping_data():
    """Fixture for creating a WeatherPlaylistMapper instance with a valid mapping file."""
    with open(
        "tests/components/spotify/test_spotify_mappings.json", encoding="utf-8"
    ) as file:
        return json.load(file)


# Fixture for initializing the WeatherPlaylistMapper with test data
@pytest.fixture
def mapper(spotify_mapping_data):
    """Fixture for initializing the WeatherPlaylistMapper with test data."""
    # Write the test data to a temporary file
    with open(
        "tests/components/spotify/test_spotify_mappings.json", "w", encoding="utf-8"
    ) as file:
        json.dump(spotify_mapping_data, file)
    # Initialize the mapper with the path to the temporary test file
    return WeatherPlaylistMapper("tests/components/spotify/test_spotify_mappings.json")


def test_init_valid_file(mapper: WeatherPlaylistMapper) -> None:
    """Test initializing WeatherPlaylistMapper with a valid mapping file."""
    assert mapper.spotify_category_mapping is not None


def test_init_invalid_file() -> None:
    """Test initializing WeatherPlaylistMapper with an invalid mapping file."""
    with pytest.raises(FileNotFoundError):
        WeatherPlaylistMapper("path/to/invalid/spotify_mappings.json")


def test_map_weather_to_playlists_valid_conditions(
    mapper: WeatherPlaylistMapper,
) -> None:
    """Test mapping weather conditions to search string with valid conditions."""
    search_string = mapper.map_weather_to_playlists(20, "sunny")
    # Expected search string for 'warm' 'sunny
    assert search_string == "Sunny Day Play"


def test_map_weather_to_playlists_invalid_condition(
    mapper: WeatherPlaylistMapper,
) -> None:
    """Test mapping weather conditions to search string with an invalid condition."""
    with pytest.raises(ValueError):
        mapper.map_weather_to_playlists(20, "sleepy")


def test_map_weather_to_playlists_boundary_temperature(
    mapper: WeatherPlaylistMapper,
) -> None:
    """Test mapping weather conditions to search string at the boundary temperature."""
    search_string = mapper.map_weather_to_playlists(15, "cloudy")
    # Expected search string for 'warm' 'cloudy
    assert search_string == "Overcast Moods"
