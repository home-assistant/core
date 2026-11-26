"""Session fixtures."""

from typing import Any

import pytest

from . import make_bluetooth_storage


@pytest.fixture
def mock_bluetooth_storage(
    hass_storage: dict[str, Any], request: pytest.FixtureRequest
) -> None:
    """Load Bluetooth storage before setting up the integration.

    Parametrize with the arguments of make_bluetooth_storage.
    """
    hass_storage.update(make_bluetooth_storage(*getattr(request, "param", ({}, {}))))


@pytest.fixture(autouse=True)
def mock_bluetooth(mock_bluetooth_storage: None, enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""
