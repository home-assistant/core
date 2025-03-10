"""Common fixtures for the aidot tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aidot.client import AidotClient
from aidot.const import CONF_ACCESS_TOKEN, CONF_ID, CONF_LOGIN_INFO
from aidot.device_client import DeviceClient, DeviceInformation, DeviceStatusData
import pytest

from homeassistant.components.aidot.const import DOMAIN
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_COUNTRY = "United States"
TEST_EMAIL = "test@gmail.com"
TEST_PASSWORD = "123456"

TEST_LOGIN_RESP = {
    "id": "314159263367458941151",
    "accessToken": "1234567891011121314151617181920",
    "refreshToken": "2021222324252627282930313233343",
    "expiresIn": 10000,
    "nickname": TEST_EMAIL,
    "username": TEST_EMAIL,
}


def mock_device_list() -> list[dict[str, Any]]:
    """Fixture for a mock device."""
    return {
        "device_list": [
            {
                "id": "device_id",
                "name": "Test Light",
                "modelId": "aidot.light.rgbw",
                "mac": "AA:BB:CC:DD:EE:FF",
                "hardwareVersion": "1.0",
                "type": "light",
                "aesKey": ["mock_aes_key"],
                "product": {
                    "id": "test_product",
                    "serviceModules": [
                        {"identity": "control.light.rgbw"},
                        {
                            "identity": "control.light.cct",
                            "properties": [
                                {"identity": "CCT", "maxValue": 6500, "minValue": 2700}
                            ],
                        },
                    ],
                },
            }
        ]
    }


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.aidot.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create and add a config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        email=TEST_EMAIL,
        password=TEST_PASSWORD,
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_EMAIL,
        title=TEST_EMAIL,
        data={
            CONF_LOGIN_INFO: {
                CONF_USERNAME: TEST_EMAIL,
                CONF_PASSWORD: TEST_PASSWORD,
                "region": "us",
                CONF_COUNTRY: TEST_COUNTRY,
                CONF_ACCESS_TOKEN: "123456789",
                CONF_ID: "123456",
            }
        },
    )
    config_entry.runtime_data = Mock()
    return config_entry


@pytest.fixture
def mocked_device_client() -> Mock:
    """Fixture DeviceClient."""
    mock_device_client = Mock(spec=DeviceClient)
    mock_device_client.async_turn_on = AsyncMock(return_value=None)
    mock_device_client.async_turn_off = AsyncMock(return_value=None)
    mock_device_client.async_set_brightness = AsyncMock(return_value=None)
    mock_device_client.async_set_cct = AsyncMock(return_value=None)
    mock_device_client.async_set_rgbw = AsyncMock(return_value=None)
    mock_device_client.close = AsyncMock(return_value=None)
    mock_device_client.async_login = AsyncMock(return_value=None)

    mock_info = Mock(spec=DeviceInformation)
    mock_info.enable_rgbw = True
    mock_info.enable_dimming = True
    mock_info.enable_cct = True
    mock_info.cct_min = 2700
    mock_info.cct_max = 6500
    mock_info.dev_id = "device_id"
    mock_info.mac = "AA:BB:CC:DD:EE:FF"
    mock_info.model_id = "aidot.light.rgbw"
    mock_info.name = "Test Light"
    mock_info.hw_version = "1.0"
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
def mocked_aidot_client(mocked_device_client) -> Mock:
    """Fixture AidotClient."""
    mock_aidot_client = Mock(spec=AidotClient)
    mock_aidot_client.get_device_client = Mock(return_value=mocked_device_client)
    mock_aidot_client.async_get_all_device = AsyncMock(return_value=mock_device_list())
    mock_aidot_client.async_post_login = AsyncMock(return_value=TEST_LOGIN_RESP)
    return mock_aidot_client


@pytest.fixture(autouse=True)
def patch_aidot_client(mocked_aidot_client):
    """Patch DeviceClient."""
    with patch(
        "homeassistant.components.aidot.coordinator.AidotClient",
        return_value=mocked_aidot_client,
    ):
        yield
