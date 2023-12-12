"""Tests for sensor."""
from homeassistant.components.krisinformation.geo_location import (
    KrisInformationGeolocationEvent,
)
from homeassistant.const import UnitOfLength


def _generate_mock_feed_entry(headline: str, latitude: float, longitude: float):
    return KrisInformationGeolocationEvent(
        headline, latitude, longitude, UnitOfLength.KILOMETERS
    )
