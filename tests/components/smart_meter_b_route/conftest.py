"""Common fixtures for the Smart Meter B-route tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.smart_meter_b_route.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
def mock_momonga(exception=None) -> Generator[Mock]:
    """Mock for Momonga class."""

    with (
        patch(
            "homeassistant.components.smart_meter_b_route.coordinator.Momonga",
            autospec=True,
        ) as mock_momonga,
        patch(
            "homeassistant.components.smart_meter_b_route.config_flow.Momonga",
            new=mock_momonga,
        ),
    ):
        client = mock_momonga.return_value
        client.__enter__.return_value = client
        client.get_instantaneous_current.return_value = {
            "r phase current": 1,
            "t phase current": 2,
        }
        client.get_instantaneous_power.return_value = 3
        client.get_measured_cumulative_energy.return_value = 4
        yield mock_momonga
