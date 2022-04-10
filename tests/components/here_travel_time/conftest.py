"""Fixtures for HERE Travel Time tests."""
import json
from unittest.mock import patch

from herepy.models import RoutingResponse
import pytest

from tests.common import load_fixture

RESPONSE = RoutingResponse.new_from_jsondict(
    json.loads(load_fixture("here_travel_time/car_response.json"))
)
RESPONSE.route_short = "US-29 - K St NW; US-29 - Whitehurst Fwy; I-495 N - Capital Beltway; MD-187 S - Old Georgetown Rd"


@pytest.fixture(name="valid_response")
def valid_response_fixture():
    """Return valid api response."""
    with patch(
        "herepy.RoutingApi.public_transport_timetable",
        return_value=RESPONSE,
    ) as mock:
        yield mock
