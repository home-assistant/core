"""Configure iCloud tests."""
from unittest.mock import patch

import pytest


@pytest.fixture(name="icloud_bypass_setup", autouse=True)
def icloud_bypass_setup_fixture():
    """Mock component setup."""
    with patch("homeassistant.components.icloud.async_setup_entry", return_value=True):
        yield


@pytest.fixture(autouse=True)
def icloud_not_create_dir():
    """Mock component setup."""
    with patch(
        "homeassistant.components.icloud.config_flow.os.path.exists", return_value=True
    ):
        yield
