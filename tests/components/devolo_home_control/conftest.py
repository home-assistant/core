"""Fixtures for tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest


@pytest.fixture
def credentials_valid() -> bool:
    """Mark test as credentials invalid."""
    return True


@pytest.fixture
def maintenance() -> bool:
    """Mark test as maintenance mode on."""
    return False


@pytest.fixture(autouse=True)
def patch_mydevolo(
    credentials_valid: bool, maintenance: bool
) -> Generator[None, None, None]:
    """Fixture to patch mydevolo into a desired state."""
    with (
        patch(
            "homeassistant.components.devolo_home_control.Mydevolo.credentials_valid",
            return_value=credentials_valid,
        ),
        patch(
            "homeassistant.components.devolo_home_control.Mydevolo.maintenance",
            return_value=maintenance,
        ),
        patch(
            "homeassistant.components.devolo_home_control.Mydevolo.get_gateway_ids",
            return_value=["1400000000000001", "1400000000000002"],
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def devolo_home_control_mock_async_zeroconf(mock_async_zeroconf):
    """Auto mock zeroconf."""
