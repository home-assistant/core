"""Common fixtures for the Qube Heat Pump tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from python_qube_heatpump.models import QubeState


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.qube_heatpump.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_qube_client():
    """Mock the QubeClient to avoid real network calls."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.host = "1.2.3.4"
        client.port = 502
        client.unit = 1
        client.connect = AsyncMock(return_value=True)
        client.is_connected = True
        client.close = AsyncMock(return_value=None)

        # Default state
        state = QubeState()
        state.temp_supply = 45.0
        state.temp_return = 40.0
        state.temp_outside = 10.0
        state.power_thermic = 5000.0
        state.power_electric = 1200.0
        state.energy_total_electric = 123.456
        state.status_code = 1

        client.get_all_data = AsyncMock(return_value=state)

        yield client
