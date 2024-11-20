"""Tests for the Airzone integration."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def airzone_cloud_no_websockets():
    """Fixture to completely disable Airzone Cloud WebSockets."""
    with (
        patch(
            "homeassistant.components.airzone_cloud.AirzoneCloudApi._update_websockets",
            return_value=False,
        ),
        patch(
            "homeassistant.components.airzone_cloud.AirzoneCloudApi.connect_installation_websockets",
            return_value=None,
        ),
    ):
        yield
