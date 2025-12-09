"""Common fixtures for the Hikvision tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry

TEST_HOST = "192.168.1.100"
TEST_PORT = 80
TEST_USERNAME = "admin"
TEST_PASSWORD = "password123"
TEST_DEVICE_ID = "DS-2CD2142FWD-I20170101AAAA"
TEST_DEVICE_NAME = "Front Camera"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.hikvision.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=TEST_DEVICE_NAME,
        domain=DOMAIN,
        version=1,
        minor_version=1,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
        unique_id=TEST_DEVICE_ID,
    )


@pytest.fixture
def mock_hikcamera() -> Generator[MagicMock]:
    """Return a mocked HikCamera."""
    with patch(
        "homeassistant.components.hikvision.HikCamera",
        autospec=True,
    ) as hikcamera_mock:
        camera = hikcamera_mock.return_value
        camera.get_id = TEST_DEVICE_ID
        camera.get_name = TEST_DEVICE_NAME
        camera.get_type = "Camera"
        camera.current_event_states = {
            "Motion": [(True, 1)],
            "Line Crossing": [(False, 1)],
        }
        camera.start_stream = MagicMock()
        camera.disconnect = MagicMock()
        camera.add_update_callback = MagicMock()
        camera.fetch_attributes = MagicMock(
            return_value=(False, None, None, "2024-01-01T00:00:00Z")
        )
        yield hikcamera_mock


@pytest.fixture
def mock_hikcamera_config_flow() -> Generator[MagicMock]:
    """Return a mocked HikCamera for config flow."""
    with patch(
        "homeassistant.components.hikvision.config_flow.HikCamera",
        autospec=True,
    ) as hikcamera_mock:
        camera = hikcamera_mock.return_value
        camera.get_id = TEST_DEVICE_ID
        camera.get_name = TEST_DEVICE_NAME
        camera.get_type = "Camera"
        yield hikcamera_mock


@pytest.fixture
def mock_get_nvr_events() -> Generator[MagicMock]:
    """Return a mocked get_nvr_events function."""
    with patch(
        "homeassistant.components.hikvision.get_nvr_events",
    ) as mock_get_nvr:
        # By default, return empty dict (no additional events)
        mock_get_nvr.return_value = {}
        yield mock_get_nvr


@pytest.fixture
def mock_inject_events() -> Generator[MagicMock]:
    """Return a mocked inject_events_into_camera function."""
    with patch(
        "homeassistant.components.hikvision.inject_events_into_camera",
    ) as mock_inject:
        yield mock_inject


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_hikcamera: MagicMock
) -> MockConfigEntry:
    """Set up the Hikvision integration for testing."""
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry
