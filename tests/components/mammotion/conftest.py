"""Fixtures for Mammotion tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from . import BLE_DEVICE_LUBA, BLE_DEVICE_YUKA

DEFAULT_NAME = "Luba-ABC123"


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_setup_entry():
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.mammotion.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture(name="discovery")
def mock_async_discovered_service_info() -> Generator[MagicMock]:
    """Mock service discovery."""
    with patch(
        "homeassistant.components.mammotion.config_flow.async_discovered_service_info",
        return_value=[BLE_DEVICE_LUBA, BLE_DEVICE_YUKA],
    ) as discovery:
        yield discovery


@pytest.fixture
def mock_cloud_gateway():
    """Mock a CloudIOTGateway."""
    mock_cloud = Mock()
    mock_cloud.mammotion_http = Mock()
    mock_cloud.mammotion_http.login_info = Mock()
    mock_cloud.mammotion_http.login_info.userInformation = Mock()
    mock_cloud.mammotion_http.login_info.userInformation.userAccount = "user123"
    return mock_cloud


@pytest.fixture
def mock_http_response():
    """Mock a successful HTTP login response."""
    mock_response = Mock()
    mock_response.login_info = Mock()
    mock_response.login_info.userInformation = Mock()
    mock_response.login_info.userInformation.userAccount = "user123"
    return mock_response


@pytest.fixture
def mock_mammotion():
    """Mock Mammotion class."""
    mock = AsyncMock()
    mock.mqtt_list = {}
    mock.login_and_initiate_cloud = AsyncMock()
    return mock


@pytest.fixture
def mock_mower_coordinator():
    """Return a mocked mower coordinator."""
    coordinator = AsyncMock()
    coordinator.data = Mock()
    coordinator.data.report_data = Mock()
    coordinator.data.report_data.dev = Mock()
    coordinator.api = Mock()
    coordinator.api.async_request_iot_sync = AsyncMock()
    return coordinator
