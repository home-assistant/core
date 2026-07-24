"""Tests for the geonetnz_quakes component."""

from unittest.mock import MagicMock


def _generate_mock_feed_entry(
    external_id,
    title,
    distance_to_home,
    coordinates,
    attribution=None,
    depth=None,
    magnitude=None,
    mmi=None,
    locality=None,
    quality=None,
    time=None,
):
    """Construct a mock feed entry for testing purposes."""
    feed_entry = MagicMock()
    feed_entry.external_id = external_id
    feed_entry.title = title
    feed_entry.distance_to_home = distance_to_home
    feed_entry.coordinates = coordinates
    feed_entry.attribution = attribution
    feed_entry.depth = depth
    feed_entry.magnitude = magnitude
    feed_entry.mmi = mmi
    feed_entry.locality = locality
    feed_entry.quality = quality
    feed_entry.time = time
    return feed_entry
