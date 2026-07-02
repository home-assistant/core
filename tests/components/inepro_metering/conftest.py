"""Define fixtures available for inepro Metering tests."""

import pytest


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock Bluetooth."""
