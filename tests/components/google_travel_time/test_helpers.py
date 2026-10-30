"""Tests for google_travel_time.helpers."""

import datetime as dt

from freezegun.api import FrozenDateTimeFactory
from google_maps_routing_api import LatLng, Location, Waypoint
import pytest

from homeassistant.components.google_travel_time import helpers
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


@pytest.mark.parametrize(
    ("location", "expected_result"),
    [
        (
            "12.34,56.78",
            Waypoint(
                location=Location(lat_lng=LatLng(latitude=12.34, longitude=56.78))
            ),
        ),
        (
            "12.34, 56.78",
            Waypoint(
                location=Location(lat_lng=LatLng(latitude=12.34, longitude=56.78))
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


def test_convert_time(freezer: FrozenDateTimeFactory) -> None:
    """Test convert_time keeps a future time today and shifts a past time."""
    freezer.move_to("2026-01-01 12:00:00+00:00")
    start_of_day = dt_util.start_of_local_day()

    future_time = helpers.convert_time("13:00:00")
    assert future_time == start_of_day + dt.timedelta(hours=13)

    past_time = helpers.convert_time("11:00:00")
    assert past_time == start_of_day + dt.timedelta(days=1, hours=11)
