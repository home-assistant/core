"""Standard fixtures for the Fjäråskupan integration."""

import pytest


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""
