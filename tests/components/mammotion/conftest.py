"""Fixtures for Mammotion tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

from pymammotion.aliyun.model.dev_by_account_response import Device
from pymammotion.client import MammotionClient
from pymammotion.data.model.device import MowingDevice
from pymammotion.homeassistant import HomeAssistantMowerApi
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.mammotion import MammotionConfigEntry
from homeassistant.components.mammotion.const import (
    CONF_ACCOUNT_ID,
    CONF_ACCOUNTNAME,
    DOMAIN,
)
from homeassistant.components.mammotion.models import MammotionDevices
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import ACCOUNT_ID, ACCOUNT_NAME, LOGIN_INFO, cloud_device


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""

    async def _setup_entry(hass: HomeAssistant, entry: MammotionConfigEntry) -> None:
        # Unloading the entry when the test ends reads its runtime data.
        entry.runtime_data = MammotionDevices([])

    with patch(
        "homeassistant.components.mammotion.async_setup_entry",
        side_effect=_setup_entry,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_mammotion_http() -> Generator[MagicMock]:
    """Mock the HTTP client the config flow validates the login with."""
    with patch(
        "homeassistant.components.mammotion.config_flow.MammotionHTTP",
        autospec=True,
    ) as mock_http:
        client: MagicMock = mock_http.return_value
        client.login_info = LOGIN_INFO
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=ACCOUNT_NAME,
        data={
            CONF_ACCOUNTNAME: ACCOUNT_NAME,
            CONF_PASSWORD: "password",
            CONF_ACCOUNT_ID: ACCOUNT_ID,
        },
        unique_id=ACCOUNT_ID,
    )


@pytest.fixture
def mock_mowing_device() -> MowingDevice:
    """Return the state of the mower as reported by the device."""
    return MowingDevice()


@pytest.fixture
def mock_cloud_devices() -> list[Device]:
    """Return the devices the cloud lists for the account."""
    return [cloud_device()]


@pytest.fixture
def mock_mower_api(
    mock_mowing_device: MowingDevice, mock_cloud_devices: list[Device]
) -> Generator[MagicMock]:
    """Mock the pymammotion mower API."""
    client = create_autospec(MammotionClient, instance=True)
    client.aliyun_device_list = mock_cloud_devices
    client.mammotion_device_list = []
    client.reauth_required = None
    client.to_cache.return_value = {}
    client.get_device_by_name.return_value = None
    client.mower.return_value = None

    api = create_autospec(HomeAssistantMowerApi, instance=True)
    api.mammotion = client
    api.update.return_value = mock_mowing_device
    api.is_online.return_value = True

    with patch(
        "homeassistant.components.mammotion.HomeAssistantMowerApi",
        return_value=api,
    ):
        yield api


@pytest.fixture
def mock_mammotion(mock_mower_api: MagicMock) -> MagicMock:
    """Return the mocked cloud client the mower API wraps."""
    return mock_mower_api.mammotion
