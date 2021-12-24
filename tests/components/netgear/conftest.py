"""Configure Netgear tests."""
from unittest.mock import patch

import pytest


@pytest.fixture(name="bypass_setup", autouse=True)
def bypass_setup_fixture():
    """Mock component setup."""
    with patch(
        "homeassistant.components.netgear.device_tracker.async_get_scanner",
        return_value=None,
    ):
        yield
