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
    """Mock for Serial class."""

    class MockMomonga:
        def __init__(self, *args, **kwargs) -> None:
            if exception:
                raise exception

        def open(self):
            pass

        def get_instantaneous_current(self) -> dict[str, float]:
            return {
                "r phase current": 1,
                "t phase current": 2,
            }

        def get_instantaneous_power(self) -> float:
            return 3

        def get_measured_cumulative_energy(self) -> float:
            return 4

    with patch(
        "homeassistant.components.smart_meter_b_route.coordinator.Momonga", MockMomonga
    ):
        yield MockMomonga
