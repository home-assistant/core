"""Fixtures for HERE Travel Time tests."""

import json
from unittest.mock import patch

import pytest

from tests.common import load_fixture

RESPONSE = json.loads(load_fixture("here_travel_time/car_response.json"))
TRANSIT_RESPONSE = json.loads(
    load_fixture("here_travel_time/transit_route_response.json")
)
NO_ATTRIBUTION_TRANSIT_RESPONSE = json.loads(
    load_fixture("here_travel_time/no_attribution_transit_route_response.json")
)
BIKE_RESPONSE = json.loads(load_fixture("here_travel_time/bike_response.json"))


@pytest.fixture(name="valid_response")
def valid_response_fixture():
    """Return valid api response."""
    with (
        patch("here_transit.HERETransitApi.route", return_value=TRANSIT_RESPONSE),
        patch(
            "here_routing.HERERoutingApi.route",
            return_value=RESPONSE,
        ) as mock,
    ):
        yield mock


@pytest.fixture(name="bike_response")
def bike_response_fixture():
    """Return valid api response."""
    with (
        patch("here_transit.HERETransitApi.route", return_value=TRANSIT_RESPONSE),
        patch(
            "here_routing.HERERoutingApi.route",
            return_value=BIKE_RESPONSE,
        ) as mock,
    ):
        yield mock


@pytest.fixture(name="no_attribution_response")
def no_attribution_response_fixture():
    """Return valid api response without attribution."""
    with (
        patch(
            "here_transit.HERETransitApi.route",
            return_value=NO_ATTRIBUTION_TRANSIT_RESPONSE,
        ),
        patch(
            "here_routing.HERERoutingApi.route",
            return_value=RESPONSE,
        ) as mock,
    ):
        yield mock
