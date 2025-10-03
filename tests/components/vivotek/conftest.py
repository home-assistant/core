"""Setup Vivotek tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.vivotek.camera import (
    CONF_FRAMERATE,
    CONF_SECURITY_LEVEL,
    CONF_STREAM_PATH,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from tests.common import MockConfigEntry

TEST_CAM_NAME = "test_cam"
TEST_MODEL_NAME = "model_123"
TEST_IP_ADDRESS = "127.1.2.3"

TEST_CONFIG: ConfigType = {
    CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
    CONF_IP_ADDRESS: TEST_IP_ADDRESS,
    CONF_NAME: TEST_CAM_NAME,
    CONF_PASSWORD: "test_pwd",
    CONF_SSL: False,
    CONF_USERNAME: "test_user",
    CONF_VERIFY_SSL: False,
    CONF_FRAMERATE: 2,
    CONF_SECURITY_LEVEL: "admin",
    CONF_STREAM_PATH: "live.sdp",
}


def _init_camera_mock(camera_mock: MagicMock) -> None:
    camera_mock.model_name = TEST_MODEL_NAME
    camera_mock.snapshot = MagicMock(return_value=b"image_bytes")
    camera_mock.get_param = MagicMock(return_value="key=1")
    camera_mock.set_param = MagicMock(return_value="key=1")


@pytest.fixture
def vivotek_camera_class() -> Generator[MagicMock]:
    """Mock vivotek connection and return both the camera_mock and camera_mock_class."""
    with patch("libpyvivotek.VivotekCamera", autospec=False) as camera_mock_class:
        _init_camera_mock(camera_mock_class.return_value)
        yield camera_mock_class


@pytest.fixture
def vivotek_camera(vivotek_camera_class: MagicMock) -> Generator[MagicMock]:
    """Mock vivotek Host class."""
    return vivotek_camera_class.return_value


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add the vivotek mock config entry to hass."""
    config_entry = MockConfigEntry(
        domain="vivotek",
        data=TEST_CONFIG,
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def add_entities(hass: HomeAssistant) -> AddEntitiesCallback:
    """Mock add_entities callback."""
    return AddEntitiesCallback()
