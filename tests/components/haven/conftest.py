"""Fixtures for HAVEN IAQ tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from haveniaq import DeviceInfo, SensorData
import pytest

from homeassistant.components.haven.const import DOMAIN
from homeassistant.const import CONF_HOST

from . import TEST_CAM_SERIAL, TEST_HOST, TEST_INFO, TEST_SENSORS, TEST_SERIAL

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config flow tests from setting up the integration."""
    with patch(
        "homeassistant.components.haven.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_haven_client_class() -> Generator[MagicMock]:
    """Mock the HAVEN client class used by setup and config flows."""
    with (
        patch(
            "homeassistant.components.haven.coordinator.HavenClient",
            autospec=True,
        ) as mock_client_class,
        patch(
            "homeassistant.components.haven.config_flow.HavenClient",
            new=mock_client_class,
        ),
    ):
        yield mock_client_class


@pytest.fixture
def mock_haven_client(mock_haven_client_class: MagicMock) -> AsyncMock:
    """Return a configured HAVEN client mock."""
    client = mock_haven_client_class.return_value
    client.get_info.return_value = DeviceInfo.from_dict(TEST_INFO)
    client.get_sensors.return_value = SensorData.from_dict(TEST_SENSORS)
    return client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a HAVEN config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Room Air Monitor",
        data={CONF_HOST: TEST_HOST},
        unique_id=TEST_SERIAL,
    )


@pytest.fixture
def mock_cam_config_entry() -> MockConfigEntry:
    """Return a Central Air Monitor config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Central Air Monitor",
        data={CONF_HOST: TEST_HOST},
        unique_id=TEST_CAM_SERIAL,
    )
