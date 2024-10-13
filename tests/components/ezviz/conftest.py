"""Define pytest.fixtures available for all tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from pyezviz import EzvizClient
from pyezviz.test_cam_rtsp import TestRTSPAuth
import pytest

from homeassistant.core import HomeAssistant

ezviz_login_token_return = {
    "session_id": "fake_token",
    "rf_session_id": "fake_rf_token",
    "api_url": "apiieu.ezvizlife.com",
}


@pytest.fixture(autouse=True)
def mock_ffmpeg(hass: HomeAssistant) -> None:
    """Mock ffmpeg is loaded."""
    hass.config.components.add("ffmpeg")


@pytest.fixture
def ezviz_test_rtsp_config_flow() -> Generator[MagicMock]:
    """Mock the EzvizApi for easier testing."""
    with (
        patch.object(TestRTSPAuth, "main", return_value=True),
        patch(
            "homeassistant.components.ezviz.config_flow.TestRTSPAuth"
        ) as mock_ezviz_test_rtsp,
    ):
        instance = mock_ezviz_test_rtsp.return_value = TestRTSPAuth(
            "test-ip",
            "test-username",
            "test-password",
        )

        instance.main = MagicMock(return_value=True)

        yield mock_ezviz_test_rtsp


@pytest.fixture
def ezviz_config_flow() -> Generator[MagicMock]:
    """Mock the EzvizAPI for easier config flow testing."""
    with (
        patch.object(EzvizClient, "login", return_value=True),
        patch("homeassistant.components.ezviz.config_flow.EzvizClient") as mock_ezviz,
    ):
        instance = mock_ezviz.return_value = EzvizClient(
            "test-username",
            "test-password",
            "local.host",
            "1",
        )

        instance.login = MagicMock(return_value=ezviz_login_token_return)
        instance.get_detection_sensibility = MagicMock(return_value=True)

        yield mock_ezviz
