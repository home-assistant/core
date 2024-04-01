"""Define fixtures available for all tests."""

from unittest.mock import MagicMock, patch

from canary.api import Api
import pytest


@pytest.fixture(autouse=True)
def mock_ffmpeg(hass):
    """Mock ffmpeg is loaded."""
    hass.config.components.add("ffmpeg")


@pytest.fixture
def canary(hass):
    """Mock the CanaryApi for easier testing."""
    with (
        patch.object(Api, "login", return_value=True),
        patch("homeassistant.components.canary.Api") as mock_canary,
    ):
        instance = mock_canary.return_value = Api(
            "test-username",
            "test-password",
            1,
        )

        instance.login = MagicMock(return_value=True)
        instance.get_entries = MagicMock(return_value=[])
        instance.get_locations = MagicMock(return_value=[])
        instance.get_location = MagicMock(return_value=None)
        instance.get_modes = MagicMock(return_value=[])
        instance.get_readings = MagicMock(return_value=[])
        instance.get_latest_readings = MagicMock(return_value=[])
        instance.set_location_mode = MagicMock(return_value=None)

        yield mock_canary


@pytest.fixture
def canary_config_flow(hass):
    """Mock the CanaryApi for easier config flow testing."""
    with (
        patch.object(Api, "login", return_value=True),
        patch("homeassistant.components.canary.config_flow.Api") as mock_canary,
    ):
        instance = mock_canary.return_value = Api(
            "test-username",
            "test-password",
            1,
        )

        instance.login = MagicMock(return_value=True)
        instance.get_entries = MagicMock(return_value=[])
        instance.get_locations = MagicMock(return_value=[])
        instance.get_location = MagicMock(return_value=None)
        instance.get_modes = MagicMock(return_value=[])
        instance.get_readings = MagicMock(return_value=[])
        instance.get_latest_readings = MagicMock(return_value=[])
        instance.set_location_mode = MagicMock(return_value=None)

        yield mock_canary
