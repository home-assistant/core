"""Tests for the geo_json_events component."""
from unittest.mock import MagicMock


def _generate_mock_feed_entry(
    external_id: str,
    title: str,
    distance_to_home: float,
    coordinates: tuple[float, float],
) -> MagicMock:
    """Construct a mock feed entry for testing purposes."""
    feed_entry = MagicMock()
    feed_entry.external_id = external_id
    feed_entry.title = title
    feed_entry.distance_to_home = distance_to_home
    feed_entry.coordinates = coordinates
    return feed_entry
