"""Tests for the GDACS component."""
from unittest.mock import MagicMock


def _generate_mock_feed_entry(
    external_id,
    title,
    distance_to_home,
    coordinates,
    attribution=None,
    alert_level=None,
    country=None,
    duration_in_week=None,
    event_name=None,
    event_type_short=None,
    event_type=None,
    from_date=None,
    to_date=None,
    population=None,
    severity=None,
    vulnerability=None,
):
    """Construct a mock feed entry for testing purposes."""
    feed_entry = MagicMock()
    feed_entry.external_id = external_id
    feed_entry.title = title
    feed_entry.distance_to_home = distance_to_home
    feed_entry.coordinates = coordinates
    feed_entry.attribution = attribution
    feed_entry.alert_level = alert_level
    feed_entry.country = country
    feed_entry.duration_in_week = duration_in_week
    feed_entry.event_name = event_name
    feed_entry.event_type_short = event_type_short
    feed_entry.event_type = event_type
    feed_entry.from_date = from_date
    feed_entry.to_date = to_date
    feed_entry.population = population
    feed_entry.severity = severity
    feed_entry.vulnerability = vulnerability
    return feed_entry
