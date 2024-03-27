"""Test waze_travel_time services."""

import pytest

from homeassistant.components.waze_travel_time.const import DEFAULT_OPTIONS
from homeassistant.core import HomeAssistant

from .const import MOCK_CONFIG


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_service_get_travel_times(hass: HomeAssistant) -> None:
    """Test service get_travel_times."""
    response_data = await hass.services.async_call(
        "waze_travel_time",
        "get_travel_times",
        {
            "origin": "location1",
            "destination": "location2",
            "vehicle_type": "car",
            "region": "us",
        },
        blocking=True,
        return_response=True,
    )
    assert response_data == {
        "routes": [
            {
                "distance": 300,
                "duration": 150,
                "name": "E1337 - Teststreet",
                "street_names": ["E1337", "IncludeThis", "Teststreet"],
            },
            {
                "distance": 500,
                "duration": 600,
                "name": "E0815 - Otherstreet",
                "street_names": ["E0815", "ExcludeThis", "Otherstreet"],
            },
        ]
    }
