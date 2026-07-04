"""mochad conftest."""

from unittest import mock

import pytest

from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(autouse=True)
def mock_pymochad_controller():
    """Mock pymochad controller to prevent real socket connections."""
    with mock.patch("homeassistant.components.mochad.controller.PyMochad"):
        yield
