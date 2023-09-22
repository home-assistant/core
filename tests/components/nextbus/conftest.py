"""Test helpers for NextBus tests."""
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_nextbus_lists(mock_nextbus: MagicMock) -> MagicMock:
    """Mock all list functions in nextbus to test validate logic."""
    instance = mock_nextbus.return_value
    instance.get_agency_list.return_value = {
        "agency": [{"tag": "sf-muni", "title": "San Francisco Muni"}]
    }
    instance.get_route_list.return_value = {
        "route": [{"tag": "F", "title": "F - Market & Wharves"}]
    }
    instance.get_route_config.return_value = {
        "route": {
            "stop": [
                {"tag": "5650", "title": "Market St & 7th St"},
                {"tag": "5651", "title": "Market St & 7th St"},
            ],
            "direction": [
                {
                    "name": "Outbound",
                    "stop": [{"tag": "5650"}],
                },
                {
                    "name": "Inbound",
                    "stop": [{"tag": "5651"}],
                },
            ],
        }
    }

    return instance
