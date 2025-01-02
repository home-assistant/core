"""Test helpers for NextBus tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from .const import BASIC_RESULTS


@pytest.fixture(
    params=[
        [
            {
                "name": "Outbound",
                "shortName": "Outbound",
                "useForUi": True,
                "stops": ["5184"],
            },
            {
                "name": "Outbound - Hidden",
                "shortName": "Outbound - Hidden",
                "useForUi": False,
                "stops": ["5651"],
            },
        ],
        [
            {
                "name": "Outbound",
                "shortName": "Outbound",
                "useForUi": True,
                "stops": ["5184"],
            },
            {
                "name": "Inbound",
                "shortName": "Inbound",
                "useForUi": True,
                "stops": ["5651"],
            },
        ],
    ]
)
def route_config_direction(request: pytest.FixtureRequest) -> Any:
    """Generate alternative directions values.

    When only one direction is returned, it is not returned as a list, but instead an object.
    """
    return request.param


@pytest.fixture
def mock_nextbus_lists(
    mock_nextbus: MagicMock, route_config_direction: Any
) -> MagicMock:
    """Mock all list functions in nextbus to test validate logic."""
    instance = mock_nextbus.return_value
    instance.agencies.return_value = [
        {
            "id": "sfmta-cis",
            "name": "San Francisco Muni CIS",
            "shortName": "SF Muni CIS",
            "region": "",
            "website": "",
            "logo": "",
            "nxbs2RedirectUrl": "",
        }
    ]

    instance.routes.return_value = [
        {
            "id": "F",
            "rev": 1057,
            "title": "F Market & Wharves",
            "description": "7am-10pm daily",
            "color": "",
            "textColor": "",
            "hidden": False,
            "timestamp": "2024-06-23T03:06:58Z",
        },
        {
            "id": "G",
            "rev": 1057,
            "title": "F Market & Wharves",
            "description": "7am-10pm daily",
            "color": "",
            "textColor": "",
            "hidden": False,
            "timestamp": "2024-06-23T03:06:58Z",
        },
    ]

    def route_details_side_effect(agency: str, route: str) -> dict:
        route = route.upper()
        return {
            "id": route,
            "rev": 1057,
            "title": f"{route} Market & Wharves",
            "description": "7am-10pm daily",
            "color": "",
            "textColor": "",
            "hidden": False,
            "boundingBox": {},
            "stops": [
                {
                    "id": "5184",
                    "lat": 37.8071299,
                    "lon": -122.41732,
                    "name": "Jones St & Beach St",
                    "code": "15184",
                    "hidden": False,
                    "showDestinationSelector": True,
                    "directions": ["F_0_var1", "F_0_var0"],
                },
                {
                    "id": "5651",
                    "lat": 37.8071299,
                    "lon": -122.41732,
                    "name": "Jones St & Beach St",
                    "code": "15651",
                    "hidden": False,
                    "showDestinationSelector": True,
                    "directions": ["F_0_var1", "F_0_var0"],
                },
            ],
            "directions": route_config_direction,
            "paths": [],
            "timestamp": "2024-06-23T03:06:58Z",
        }

    instance.route_details.side_effect = route_details_side_effect

    return instance


@pytest.fixture
def mock_nextbus() -> Generator[MagicMock]:
    """Create a mock py_nextbus module."""
    with patch("homeassistant.components.nextbus.coordinator.NextBusClient") as client:
        yield client


@pytest.fixture
def mock_nextbus_predictions(
    mock_nextbus: MagicMock,
) -> Generator[MagicMock]:
    """Create a mock of NextBusClient predictions."""
    instance = mock_nextbus.return_value
    instance.predictions_for_stop.return_value = BASIC_RESULTS

    return instance.predictions_for_stop
