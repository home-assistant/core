"""Common fixtures for tests."""

from unittest.mock import patch

import pytest
from rointesdk.rointe_api import ApiResponse


@pytest.fixture(name="setup_rointe_login_ok")
async def setup_rointe_login_ok(hass):
    """Define a fixture to set up Rointe."""
    with (
        patch(
            "homeassistant.components.rointe.config_flow.RointeAPI.initialize_authentication",
            return_value=ApiResponse(True, None, None),
        ),
        patch(
            "homeassistant.components.rointe.config_flow.RointeAPI.is_logged_in",
            return_value=True,
        ),
    ):
        yield
