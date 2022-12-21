"""Tests for the NSW Rural Fire Service Feeds integration."""
from unittest.mock import MagicMock


def _generate_mock_feed_entry(
    external_id,
    title,
    distance_to_home,
    coordinates,
    category=None,
    location=None,
    attribution=None,
    publication_date=None,
    council_area=None,
    status=None,
    entry_type=None,
    fire=True,
    size=None,
    responsible_agency=None,
):
    """Construct a mock feed entry for testing purposes."""
    feed_entry = MagicMock()
    feed_entry.external_id = external_id
    feed_entry.title = title
    feed_entry.distance_to_home = distance_to_home
    feed_entry.coordinates = coordinates
    feed_entry.category = category
    feed_entry.location = location
    feed_entry.attribution = attribution
    feed_entry.publication_date = publication_date
    feed_entry.council_area = council_area
    feed_entry.status = status
    feed_entry.type = entry_type
    feed_entry.fire = fire
    feed_entry.size = size
    feed_entry.responsible_agency = responsible_agency
    return feed_entry
