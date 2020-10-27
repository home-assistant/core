"""Fixtures for tests."""

import pytest

from tests.async_mock import patch


@pytest.fixture()
def patch_mydevolo():
    """Fixture to patch mydevolo into a desired state."""
    with patch(
        "homeassistant.components.devolo_home_control.Mydevolo.credentials_valid",
        return_value=True,
    ):
        yield
