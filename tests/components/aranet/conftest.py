"""Aranet session fixtures."""

from typing import Any

import pytest


@pytest.fixture
def mock_bluetooth_storage(
    hass_storage: dict[str, Any], request: pytest.FixtureRequest
) -> None:
    """Load Bluetooth storage before setting up the integration."""
    hass_storage.update(getattr(request, "param", {}))


@pytest.fixture(autouse=True)
def mock_bluetooth(mock_bluetooth_storage: None, enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""
