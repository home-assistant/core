"""Common fixtures for the igloohome tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from igloohome_api import GetDeviceInfoResponse, GetDevicesResponse, LinkedDevice
import pytest

from homeassistant.components.igloohome.const import DOMAIN
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

GET_DEVICE_INFO_RESPONSE_LOCK = GetDeviceInfoResponse(
    id="123456",
    type="Lock",
    deviceId="OE1X123cbb11",
    deviceName="Front Door",
    pairedAt="2024-11-09T11:19:25+00:00",
    homeId=[],
    linkedDevices=[],
    batteryLevel=100,
)

GET_DEVICE_INFO_RESPONSE_BRIDGE_LINKED_LOCK = GetDeviceInfoResponse(
    id="001",
    type="Bridge",
    deviceId="EB1X04eeeeee",
    deviceName="Home Bridge",
    pairedAt="2024-11-09T12:19:25+00:00",
    homeId=[],
    linkedDevices=[LinkedDevice(type="Lock", deviceId="OE1X123cbb11")],
    batteryLevel=None,
)

GET_DEVICE_INFO_RESPONSE_BRIDGE_NO_LINKED_DEVICE = GetDeviceInfoResponse(
    id="001",
    type="Bridge",
    deviceId="EB1X04eeeeee",
    deviceName="Home Bridge",
    pairedAt="2024-11-09T12:19:25+00:00",
    homeId=[],
    linkedDevices=[],
    batteryLevel=None,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.igloohome.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def mock_auth() -> Generator[AsyncMock]:
    """Set up the mock usages of the igloohome_api.Auth class. Defaults to always successfully operate."""
    with patch(
        "homeassistant.components.igloohome.config_flow.IgloohomeAuth.async_get_access_token",
        return_value="mock_access_token",
    ) as mock_auth:
        yield mock_auth


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Client Credentials",
        domain=DOMAIN,
        version=1,
        data={CONF_CLIENT_ID: "client-id", CONF_CLIENT_SECRET: "client-secret"},
    )


@pytest.fixture(autouse=True)
def mock_api() -> Generator[AsyncMock]:
    """Set up the Api module. Defaults to always returning a single lock."""
    with (
        patch(
            "homeassistant.components.igloohome.IgloohomeApi",
            autospec=True,
        ) as api_mock,
    ):
        api = api_mock.return_value
        api.get_devices.return_value = GetDevicesResponse(
            nextCursor="",
            payload=[
                GET_DEVICE_INFO_RESPONSE_LOCK,
                GET_DEVICE_INFO_RESPONSE_BRIDGE_LINKED_LOCK,
            ],
        )
        api.get_device_info.return_value = GET_DEVICE_INFO_RESPONSE_LOCK
        yield api
