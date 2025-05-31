"""Tests for google_travel_time.helpers."""

from google.maps.routing_v2 import Location, Waypoint
from google.type import latlng_pb2
import pytest

from homeassistant.components.google_travel_time import helpers
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("location", "expected_result"),
    [
        (
            "12.34,56.78",
            Waypoint(
                location=Location(
                    lat_lng=latlng_pb2.LatLng(
                        latitude=12.34,
                        longitude=56.78,
                    )
                )
            ),
        ),
        (
            "12.34, 56.78",
            Waypoint(
                location=Location(
                    lat_lng=latlng_pb2.LatLng(
                        latitude=12.34,
                        longitude=56.78,
                    )
                )
            ),
        ),
        ("Some Address", Waypoint(address="Some Address")),
        ("Some Street 1, 12345 City", Waypoint(address="Some Street 1, 12345 City")),
    ],
)
def test_convert_to_waypoint_coordinates(
    hass: HomeAssistant, location: str, expected_result: Waypoint
) -> None:
    """Test convert_to_waypoint returns correct Waypoint for coordinates or address."""
    waypoint = helpers.convert_to_waypoint(hass, location)

    assert waypoint == expected_result
