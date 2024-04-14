"""yeelight conftest."""

import pytest

from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(autouse=True)
def yeelight_mock_get_source_ip(mock_get_source_ip):
    """Mock network util's async_get_source_ip."""
