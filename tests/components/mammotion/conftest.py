"""Fixtures for Mammotion tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from pymammotion.data.model.device import MowingDevice
import pytest

from homeassistant.components.mammotion.const import (
    CONF_ACCOUNT_ID,
    CONF_ACCOUNTNAME,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD

from tests.common import MockConfigEntry

DEFAULT_NAME = "Luba-ABC123"


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.mammotion.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="user@example.com",
        data={
            CONF_ACCOUNTNAME: "user@example.com",
            CONF_PASSWORD: "password",
            CONF_ACCOUNT_ID: "user123",
        },
        unique_id="user123",
    )


@pytest.fixture
def mock_mowing_device() -> MowingDevice:
    """Return the state of the mower as reported by the device."""
    return MowingDevice()


@pytest.fixture
def mock_mower_api(mock_mowing_device: MowingDevice) -> Generator[MagicMock]:
    """Mock the pymammotion mower API."""
    device = Mock()
    device.device_name = DEFAULT_NAME
    device.nick_name = "Luba"
    device.product_model = "Luba 2 AWD"

    api = MagicMock()
    api.update = AsyncMock(return_value=mock_mowing_device)
    api.is_online = Mock(return_value=True)
    api.async_send_command = AsyncMock(return_value=True)
    api.async_request_iot_sync = AsyncMock()
    api.mammotion.login_and_initiate_cloud = AsyncMock()
    api.mammotion.restore_credentials = AsyncMock()
    api.mammotion.stop = AsyncMock()
    api.mammotion.remove_device = AsyncMock()
    api.mammotion.to_cache = Mock(return_value={})
    api.mammotion.get_device_by_name = Mock(return_value=None)
    api.mammotion.mower = Mock(return_value=None)
    api.mammotion.aliyun_device_list = [device]
    api.mammotion.mammotion_device_list = []

    with patch(
        "homeassistant.components.mammotion.HomeAssistantMowerApi",
        return_value=api,
    ):
        yield api
