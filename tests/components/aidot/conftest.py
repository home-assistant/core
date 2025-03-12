"""Common fixtures for the aidot tests."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aidot.client import AidotClient
from aidot.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_LIST,
    CONF_HARDWARE_VERSION,
    CONF_ID,
    CONF_LOGIN_INFO,
    CONF_MAC,
    CONF_MODEL_ID,
    CONF_NAME,
)
from aidot.device_client import DeviceClient, DeviceInformation, DeviceStatusData
import pytest

from homeassistant.components.aidot.const import DOMAIN
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

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

ENTITY_LIGHT = "light.test_light"
ENTITY_LIGHT2 = "light.test_light2"
LIGHT_DOMAIN = "light"

TEST_DEVICE1 = {
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
                "properties": [{"identity": "CCT", "maxValue": 6500, "minValue": 2700}],
            },
        ],
    },
}

TEST_DEVICE2 = {
    "id": "device_id2",
    "name": "Test Light2",
    "modelId": "aidot.light.rgbw",
    "mac": "AA:BB:CC:DD:EE:EE",
    "hardwareVersion": "1.0",
    "type": "light",
    "aesKey": ["mock_aes_key"],
    "product": {
        "id": "test_product",
        "serviceModules": [
            {"identity": "control.light.rgbw"},
            {
                "identity": "control.light.cct",
                "properties": [{"identity": "CCT", "maxValue": 6500, "minValue": 2700}],
            },
        ],
    },
}

TEST_DEVICE_LIST = {CONF_DEVICE_LIST: [TEST_DEVICE1]}
TEST_MULTI_DEVICE_LIST = {CONF_DEVICE_LIST: [TEST_DEVICE1, TEST_DEVICE2]}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
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
