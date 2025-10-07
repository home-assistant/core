"""Tests for the Airzone integration."""

from unittest.mock import patch

from aioairzone_cloud.cloudapi import AirzoneCloudApi
import pytest


class MockAirzoneCloudApi(AirzoneCloudApi):
    """Mock AirzoneCloudApi class."""

    async def mock_update(self):
        """Mock AirzoneCloudApi _update function."""
        await self.update_polling()


@pytest.fixture(autouse=True)
def airzone_cloud_no_websockets():
    """Fixture to completely disable Airzone Cloud WebSockets."""
    with (
        patch(
            "homeassistant.components.airzone_cloud.AirzoneCloudApi._update",
            side_effect=MockAirzoneCloudApi.mock_update,
            autospec=True,
        ),
        patch(
            "homeassistant.components.airzone_cloud.AirzoneCloudApi.connect_installation_websockets",
            return_value=None,
        ),
        patch(
            "homeassistant.components.airzone_cloud.AirzoneCloudApi.update_websockets",
            return_value=None,
        ),
    ):
        yield
