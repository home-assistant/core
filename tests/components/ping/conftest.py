"""Test configuration for ping."""
from unittest.mock import patch

import pytest


@pytest.fixture
def patch_setup(*args, **kwargs):
    """Patch setup methods."""
    with patch(
        "homeassistant.components.ping.async_setup_entry",
        return_value=True,
    ), patch("homeassistant.components.ping.async_setup", return_value=True):
        yield
