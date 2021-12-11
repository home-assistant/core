"""Fixtures for tests."""

from unittest.mock import patch

import pytest


def pytest_configure(config):
    """Define custom markers."""
    config.addinivalue_line(
        "markers",
        "credentials_invalid: Treat credentials as invalid.",
    )
    config.addinivalue_line(
        "markers",
        "maintenance: Set maintenance mode to on.",
    )


@pytest.fixture(autouse=True)
def patch_mydevolo(request):
    """Fixture to patch mydevolo into a desired state."""
    with patch(
        "homeassistant.components.devolo_home_control.Mydevolo.credentials_valid",
        return_value=not bool(request.node.get_closest_marker("credentials_invalid")),
    ), patch(
        "homeassistant.components.devolo_home_control.Mydevolo.maintenance",
        return_value=bool(request.node.get_closest_marker("maintenance")),
    ), patch(
        "homeassistant.components.devolo_home_control.Mydevolo.get_gateway_ids",
        return_value=["1400000000000001", "1400000000000002"],
    ):
        yield


@pytest.fixture(autouse=True)
def devolo_home_control_mock_async_zeroconf(mock_async_zeroconf):
    """Auto mock zeroconf."""
