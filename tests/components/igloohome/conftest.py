"""Common fixtures for the igloohome tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from igloohome_api import GetDeviceInfoResponse, GetDevicesResponse
import pytest

from homeassistant.components.igloohome.const import DOMAIN
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


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.igloohome.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def mock_auth() -> Generator[MagicMock]:
    """Mock the auth class."""
    with (
            patch(
            "igloohome_api.Auth.",
            autospec=True
        ) as mock_auth,
        patch(
            "igloohome_api.config_flow.Auth",
            new=mock_auth,
        )
    ):
        auth = mock_auth.return_value
        auth.async_get_access_token.return_value = True
        yield auth


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Client Credentials",
        domain=DOMAIN,
        version=1,
        data={"client_id": "client_id", "client_secret": "client_secret"},
    )


@pytest.fixture(autouse=True)
def api_single_lock():
    """Set up Api module to always return a single lock type device."""
    with (
        patch(
            "homeassistant.components.igloohome.IgloohomeApi",
            autospec=True,
        ) as api_mock,
    ):
        api = api_mock.return_value
        api.get_devices = AsyncMock(
            return_value=GetDevicesResponse(
                nextCursor="",
                payload=[GET_DEVICE_INFO_RESPONSE_LOCK],
            )
        )
        api.get_device_info = AsyncMock(return_value=GET_DEVICE_INFO_RESPONSE_LOCK)
        yield api
