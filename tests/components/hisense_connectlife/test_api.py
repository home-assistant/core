"""Tests for Hisense ConnectLife API client."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from connectlife_cloud import ConnectLifeCloudClient, ConnectLifeWebSocket
import pytest

from homeassistant.components.hisense_connectlife.api import HisenseApiClient
from homeassistant.components.hisense_connectlife.models import (
    DeviceInfo,
    HisenseApiError,
)
from homeassistant.components.hisense_connectlife.oauth2 import OAuth2Session
from homeassistant.core import HomeAssistant

DEVICE_ID = "test_device_123"
PUID = "test_puid_123"
ACCESS_TOKEN = "test_token_123"


@pytest.fixture
async def oauth_session() -> AsyncGenerator[OAuth2Session]:
    """Fixture for OAuth2 session."""
    session = MagicMock(spec=OAuth2Session)
    session.async_get_access_token = AsyncMock(return_value=ACCESS_TOKEN)
    session.session = MagicMock()
    return session


@pytest.fixture
async def mock_cloud_client() -> AsyncGenerator[ConnectLifeCloudClient]:
    """Fixture for mocked ConnectLifeCloudClient."""
    with patch(
        "homeassistant.components.hisense_connectlife.api.ConnectLifeCloudClient"
    ) as mock:
        client = mock.return_value
        client.session = MagicMock()
        client.get_devices_with_parsers = AsyncMock(return_value={})
        client.update_power_consumption = AsyncMock()
        client.update_self_check_data = AsyncMock()
        client.parse_device_status = MagicMock(return_value={"status": "ok"})
        client.control_device = AsyncMock(return_value={"success": True})
        client.get_parser = MagicMock(return_value=None)
        client.close = AsyncMock()
        client._parsers = {}
        client._static_data = {}
        yield client


@pytest.fixture
async def api_client(
    hass: HomeAssistant,
    oauth_session: OAuth2Session,
    mock_cloud_client: ConnectLifeCloudClient,
) -> AsyncGenerator[HisenseApiClient]:
    """Fixture for Hisense API client."""
    client = HisenseApiClient(hass, oauth_session)
    yield client
    await client.async_cleanup()


async def test_initialization(
    api_client: HisenseApiClient,
    mock_cloud_client: ConnectLifeCloudClient,
) -> None:
    """Test API client initialization."""
    assert api_client is not None
    assert api_client.hass is not None
    assert api_client.oauth_session is not None
    assert api_client.client == mock_cloud_client
    assert api_client._devices == {}
    assert api_client._websocket is None


async def test_async_get_devices_empty(
    api_client: HisenseApiClient,
    mock_cloud_client: ConnectLifeCloudClient,
) -> None:
    """Test getting empty device list."""
    devices = await api_client.async_get_devices()
    assert devices == {}
    mock_cloud_client.get_devices_with_parsers.assert_awaited_once_with(ACCESS_TOKEN)


async def test_async_get_devices_with_power_consumption(
    api_client: HisenseApiClient,
    mock_cloud_client: ConnectLifeCloudClient,
) -> None:
    """Test getting devices with power consumption support."""
    mock_device = MagicMock()
    mock_device.to_dict = MagicMock(return_value={"device_id": DEVICE_ID})

    mock_parser = MagicMock()
    mock_parser.attributes = ["f_power_consumption"]

    mock_cloud_client.get_devices_with_parsers.return_value = {
        DEVICE_ID: (mock_device, mock_parser)
    }

    devices = await api_client.async_get_devices()

    assert DEVICE_ID in devices
    mock_cloud_client.update_power_consumption.assert_awaited_once()
    mock_cloud_client.update_self_check_data.assert_awaited_once()


async def test_async_get_devices_power_consumption_error(
    api_client: HisenseApiClient,
    mock_cloud_client: ConnectLifeCloudClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test power consumption update failure is handled."""
    mock_device = MagicMock()
    mock_device.to_dict = MagicMock(return_value={"device_id": DEVICE_ID})

    mock_parser = MagicMock()
    mock_parser.attributes = ["f_power_consumption"]

    mock_cloud_client.get_devices_with_parsers.return_value = {
        DEVICE_ID: (mock_device, mock_parser)
    }
    mock_cloud_client.update_power_consumption.side_effect = aiohttp.ClientError(
        "Network error"
    )

    devices = await api_client.async_get_devices()

    assert DEVICE_ID in devices
    assert "Network error updating power consumption" in caplog.text


async def test_async_get_devices_self_check_error(
    api_client: HisenseApiClient,
    mock_cloud_client: ConnectLifeCloudClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test self-check update failure is handled."""
    mock_device = MagicMock()
    mock_device.to_dict = MagicMock(return_value={"device_id": DEVICE_ID})

    mock_parser = MagicMock()
    mock_parser.attributes = []

    mock_cloud_client.get_devices_with_parsers.return_value = {
        DEVICE_ID: (mock_device, mock_parser)
    }
    mock_cloud_client.update_self_check_data.side_effect = TimeoutError("Timeout")

    devices = await api_client.async_get_devices()

    assert DEVICE_ID in devices
    assert "Network error updating self-check data" in caplog.text


async def test_async_get_devices_api_error(
    api_client: HisenseApiClient,
) -> None:
    """Test API error during device fetch."""
    api_client.client.get_devices_with_parsers.side_effect = Exception("API Down")

    with pytest.raises(HisenseApiError) as exc_info:
        await api_client.async_get_devices()

    assert "Error communicating with API" in str(exc_info.value)


async def test_async_setup_websocket(
    hass: HomeAssistant,
    api_client: HisenseApiClient,
) -> None:
    """Test WebSocket setup."""
    callback = MagicMock()

    mock_ws_instance = AsyncMock(spec=ConnectLifeWebSocket)
    mock_ws_instance.async_connect = AsyncMock()

    with patch(
        "homeassistant.components.hisense_connectlife.api.ConnectLifeWebSocket",
        return_value=mock_ws_instance,
    ):
        await api_client.async_setup_websocket(callback)
        mock_ws_instance.async_connect.assert_awaited_once()
        assert api_client._websocket is not None


async def test_async_cleanup(
    api_client: HisenseApiClient,
) -> None:
    """Test resource cleanup."""
    mock_ws = AsyncMock(spec=ConnectLifeWebSocket)
    api_client._websocket = mock_ws
    api_client.client.close = AsyncMock()

    await api_client.async_cleanup()

    mock_ws.async_disconnect.assert_awaited_once()
    api_client.client.close.assert_awaited_once()
    assert api_client._websocket is None


async def test_get_device_status_exists(
    api_client: HisenseApiClient,
) -> None:
    """Test get status for existing device."""

    api_client._devices[DEVICE_ID] = DeviceInfo({"status": {}})

    status = await api_client.get_device_status(DEVICE_ID)
    assert status == {"status": "ok"}


async def test_get_device_status_refresh(
    api_client: HisenseApiClient,
) -> None:
    """Test get status triggers device refresh."""

    mock_device = MagicMock()
    mock_device.to_dict.return_value = {"device_id": DEVICE_ID}
    api_client.client.get_devices_with_parsers.return_value = {
        DEVICE_ID: (mock_device, MagicMock())
    }

    status = await api_client.get_device_status(DEVICE_ID)
    assert status == {"status": "ok"}


async def test_get_device_status_not_found(
    api_client: HisenseApiClient,
) -> None:
    """Test device not found error."""
    api_client.async_get_devices = AsyncMock(return_value={})

    with pytest.raises(HisenseApiError) as exc_info:
        await api_client.get_device_status(DEVICE_ID)

    assert "Device not found" in str(exc_info.value)


async def test_async_control_device_success(
    api_client: HisenseApiClient,
) -> None:
    """Test successful device control."""
    properties = {"power": True, "mode": "cool"}
    response = await api_client.async_control_device(PUID, properties)

    assert response["success"] is True
    api_client.client.control_device.assert_awaited_once()


async def test_async_control_device_failure(
    api_client: HisenseApiClient,
) -> None:
    """Test device control failure."""
    api_client.client.control_device.return_value = {"success": False}

    with pytest.raises(HisenseApiError) as exc_info:
        await api_client.async_control_device(PUID, {"power": True})

    assert "Control failed" in str(exc_info.value)


async def test_async_control_device_exception(
    api_client: HisenseApiClient,
) -> None:
    """Test exception during device control."""
    api_client.client.control_device.side_effect = Exception("Error")

    with pytest.raises(HisenseApiError) as exc_info:
        await api_client.async_control_device(PUID, {"power": True})

    assert "Failed to control device" in str(exc_info.value)


async def test_get_parser(
    api_client: HisenseApiClient,
) -> None:
    """Test get device parser."""
    parser = api_client.get_parser(DEVICE_ID)
    api_client.client.get_parser.assert_called_once_with(DEVICE_ID)
    assert parser is None


async def test_parsers_property(
    api_client: HisenseApiClient,
) -> None:
    """Test parsers property."""
    assert api_client.parsers == api_client.client._parsers


async def test_static_data_property(
    api_client: HisenseApiClient,
) -> None:
    """Test static data property."""
    assert api_client.static_data == api_client.client._static_data
