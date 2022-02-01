"""Global fixtures for Unmanic integration."""
from unittest.mock import patch

import pytest


@pytest.fixture(name="error_on_get_data")
def error_get_data_fixture():
    """Simulate error when retrieving data from API."""
    with patch(
        "homeassistant.components.unmanic.UnmanicUpdateCoordinator._async_update_data",
        side_effect=Exception,
    ):
        yield
