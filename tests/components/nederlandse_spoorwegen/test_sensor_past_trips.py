"""Test NSTripSensor state when all trips are in the past."""

from datetime import UTC, datetime
from typing import Any

import pytest

from homeassistant.components.nederlandse_spoorwegen.sensor import NSTripSensor
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_update_all_trips_in_past(hass: HomeAssistant) -> None:
    """Test NSTripSensor state is 'no_trip' if all trips are in the past."""

    # Dummy trip with a planned departure in the past
    class DummyTrip:
        def __init__(self, planned, actual=None) -> None:
            self.departure_time_planned = planned
            self.departure_time_actual = actual

    # Minimal stub for NSDataUpdateCoordinator
    class DummyCoordinator:
        last_update_success = True
        data: dict[str, Any] = {
            "routes": {
                "route-uuid": {
                    "route": {
                        "route_id": "route-uuid",
                        "name": "Test Route",
                        "from": "AMS",
                        "to": "UTR",
                        "via": "",
                        "time": "",
                    },
                    "trips": [
                        DummyTrip(datetime(2024, 1, 1, 11, 0, 0, tzinfo=UTC)),
                    ],
                    "first_trip": None,
                    "next_trip": None,
                }
            },
            "stations": [],
        }

    # Minimal ConfigEntry stub
    class DummyEntry:
        entry_id = "dummy-entry"

    route = DummyCoordinator.data["routes"]["route-uuid"]["route"]
    sensor = NSTripSensor(DummyCoordinator(), DummyEntry(), route, "route-uuid")  # type: ignore[arg-type]
    assert sensor.native_value == "no_trip"
    assert sensor.available is True
