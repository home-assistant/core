"""Test helpers for Hue."""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def no_request_delay():
    """Make the request refresh delay 0 for instant tests."""
    with patch("homeassistant.components.hue.light.REQUEST_REFRESH_DELAY", 0):
        yield
