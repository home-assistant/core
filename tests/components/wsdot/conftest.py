"""Provide common WSDOT fixtures."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from wsdot import TravelTime

from homeassistant.components.wsdot.sensor import DOMAIN

from tests.common import load_json_object_fixture


@pytest.fixture
def mock_travel_time() -> AsyncGenerator[TravelTime]:
    """WsdotTravelTimes.get_travel_time is mocked to return a TravelTime data based on test fixture payload."""
    with patch(
        "homeassistant.components.wsdot.sensor.WsdotTravelTimes", autospec=True
    ) as mock:
        client = mock.return_value
        client.get_travel_time.return_value = TravelTime(
            **load_json_object_fixture("wsdot.json", DOMAIN)
        )
        yield mock
