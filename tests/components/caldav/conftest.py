"""caldav session fixtures."""

from unittest.mock import patch

import pytest


@pytest.fixture
def mock_connect():
    """Mock the dav client."""
    with patch(
        "homeassistant.components.caldav.caldav.DAVClient.principal",
    ):
        yield
