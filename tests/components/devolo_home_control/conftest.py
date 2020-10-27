"""Fixtures for tests."""

import pytest

from tests.async_mock import patch


def pytest_configure(config):
    """Define custom markers."""
    config.addinivalue_line(
        "markers",
        "credentials_valid: Define, if credentials shall be valid or not.",
    )
    config.addinivalue_line(
        "markers",
        "maintenance: Define, if maintenance mode shall be active or not.",
    )


@pytest.fixture()
def patch_mydevolo(request):
    """Fixture to patch mydevolo into a desired state."""
    with patch(
        "homeassistant.components.devolo_home_control.Mydevolo.credentials_valid",
        return_value=request.node.get_closest_marker("credentials_valid").args[0],
    ), patch(
        "homeassistant.components.devolo_home_control.Mydevolo.maintenance",
        return_value=request.node.get_closest_marker("maintenance").args[0],
    ), patch(
        "homeassistant.components.devolo_home_control.Mydevolo.get_gateway_ids",
        return_value=["1400000000000001", "1400000000000002"],
    ):
        yield
