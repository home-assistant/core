"""The tests for the GeoNet NZ Volcano Feed integration."""
from tests.async_mock import MagicMock


def _generate_mock_feed_entry(
    external_id,
    title,
    alert_level,
    distance_to_home,
    coordinates,
    attribution=None,
    activity=None,
    hazards=None,
):
    """Construct a mock feed entry for testing purposes."""
    feed_entry = MagicMock()
    feed_entry.external_id = external_id
    feed_entry.title = title
    feed_entry.alert_level = alert_level
    feed_entry.distance_to_home = distance_to_home
    feed_entry.coordinates = coordinates
    feed_entry.attribution = attribution
    feed_entry.activity = activity
    feed_entry.hazards = hazards
    return feed_entry
