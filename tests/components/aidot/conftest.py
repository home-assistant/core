"""Common fixtures for the aidot tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aidot.client import AidotClient
from aidot.const import (
    CONF_ACCESS_TOKEN,
    CONF_HARDWARE_VERSION,
    CONF_ID,
    CONF_LOGIN_INFO,
    CONF_MAC,
    CONF_MODEL_ID,
    CONF_NAME,
    CONF_REGION,
)
from aidot.device_client import DeviceClient, DeviceInformation, DeviceStatusData
import pytest

from homeassistant.components.aidot.const import DOMAIN
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .const import (
    TEST_COUNTRY,
    TEST_DEVICE1,
    TEST_DEVICE_LIST,
    TEST_EMAIL,
    TEST_LOGIN_RESP,
    TEST_PASSWORD,
    TEST_REGION,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.aidot.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{TEST_REGION}-{TEST_EMAIL}",
        title=TEST_EMAIL,
        data={
            CONF_LOGIN_INFO: {
                CONF_USERNAME: TEST_EMAIL,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_REGION: TEST_REGION,
                CONF_COUNTRY: TEST_COUNTRY,
                CONF_ACCESS_TOKEN: "123456789",
                CONF_ID: "123456",
            }
        },
    )


def create_device_client(device: dict[str, Any]) -> MagicMock:
    """Create DeviceClient."""
    mock_device_client = MagicMock(spec=DeviceClient)
    mock_device_client.device_id = device.get(CONF_ID)

    mock_info = Mock(spec=DeviceInformation)
    mock_info.enable_rgbw = True
    mock_info.enable_dimming = True
    mock_info.enable_cct = True
    mock_info.cct_min = 2700
    mock_info.cct_max = 6500
    mock_info.dev_id = device.get(CONF_ID)
    mock_info.mac = device.get(CONF_MAC)
    mock_info.model_id = device.get(CONF_MODEL_ID)
    mock_info.name = device.get(CONF_NAME)
    mock_info.hw_version = device.get(CONF_HARDWARE_VERSION)
    mock_device_client.info = mock_info

    status = Mock(spec=DeviceStatusData)
    status.online = True
    status.dimming = 255
    status.cct = 3000
    status.on = True
    status.rgbw = (255, 255, 255, 255)
    mock_device_client.status = status
    mock_device_client.read_status = AsyncMock(return_value=status)

    return mock_device_client


@pytest.fixture
def mocked_device_client() -> MagicMock:
    """Fixture DeviceClient."""
    return create_device_client(TEST_DEVICE1)


@pytest.fixture
def mocked_aidot_client(mocked_device_client) -> MagicMock:
    """Fixture AidotClient."""

    @callback
    def get_device_client(device: dict[str, Any]):
        if device.get(CONF_ID) == "device_id":
            return mocked_device_client
        return create_device_client(device)

    mock_aidot_client = MagicMock(spec=AidotClient)
    mock_aidot_client.get_device_client = get_device_client
    mock_aidot_client.async_get_all_device.return_value = TEST_DEVICE_LIST
    mock_aidot_client.async_post_login.return_value = TEST_LOGIN_RESP
    mock_aidot_client.get_identifier.return_value = f"{TEST_REGION}-{TEST_EMAIL}"
    return mock_aidot_client


@pytest.fixture(autouse=True)
def patch_aidot_client(mocked_aidot_client):
    """Patch DeviceClient."""
    with (
        patch(
            "homeassistant.components.aidot.config_flow.AidotClient",
            return_value=mocked_aidot_client,
        ),
        patch(
            "homeassistant.components.aidot.coordinator.AidotClient",
            return_value=mocked_aidot_client,
        ),
    ):
        yield
