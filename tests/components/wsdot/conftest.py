"""Provide common WSDOT fixtures."""

import json

import pytest
import wsdot

from tests.common import load_fixture


@pytest.fixture
def mock_travel_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WsdotTravelTimes.get_travel_time is mocked to return a TravelTime data based on test fixture payload."""
    test_data = load_fixture("wsdot/wsdot.json")
    test_response = json.loads(test_data)
    test_travel_time = wsdot.TravelTime(**test_response)

    async def fake_travel_time(
        self: wsdot.WsdotTravelTimes, id: str
    ) -> wsdot.TravelTime:
        return test_travel_time

    monkeypatch.setattr(wsdot.WsdotTravelTimes, "get_travel_time", fake_travel_time)
