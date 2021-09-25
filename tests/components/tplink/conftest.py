"""tplink conftest."""
from unittest.mock import patch

import pytest

from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture
def mock_discovery():
    """Mock python-kasa discovery."""
    with patch("homeassistant.components.tplink.Discover.discover") as mock_discover:
        mock_discover.return_value = {}
        yield mock_discover
