"""Test the DayBetter API client."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.daybetter_services.daybetter_api import DayBetterApi


@pytest.fixture
def mock_client():
    """Create a mock DayBetter client."""
    client = AsyncMock()
    client.integrate = AsyncMock()
    client.fetch_devices = AsyncMock()
    client.fetch_pids = AsyncMock()
    client.fetch_device_statuses = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def api_client(mock_client):
    """Create an API client instance with mocked client."""
    with patch(
        "homeassistant.components.daybetter_services.daybetter_api.DayBetterClient",
        return_value=mock_client,
    ):
        return DayBetterApi(token="test_token_12345")


class TestDayBetterApi:
    """Test DayBetter API."""

    async def test_integrate_success(self, mock_client):
        """Test successful integration."""
        mock_client.integrate.return_value = {
            "code": 1,
            "data": {"hassCodeToken": "new_token_123"},
        }

        with patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterClient",
            return_value=mock_client,
        ):
            api = DayBetterApi()
            result = await api.integrate("test_code")

            assert result["code"] == 1
            assert result["data"]["hassCodeToken"] == "new_token_123"
            mock_client.integrate.assert_called_once_with(hass_code="test_code")

    async def test_fetch_devices_success(self, api_client, mock_client):
        """Test fetching devices successfully."""
        mock_client.fetch_devices.return_value = {
            "code": 1,
            "data": [{"id": "device1", "deviceName": "Test Device"}],
        }

        result = await api_client.fetch_devices()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == "device1"
        mock_client.fetch_devices.assert_called_once()

    async def test_fetch_devices_failure(self, api_client, mock_client):
        """Test fetch devices failure."""
        mock_client.fetch_devices.return_value = {"code": 0, "msg": "Error"}

        result = await api_client.fetch_devices()

        assert result == []
        mock_client.fetch_devices.assert_called_once()

    async def test_fetch_devices_exception(self, api_client, mock_client):
        """Test fetch devices with exception."""
        mock_client.fetch_devices.side_effect = Exception("Network error")

        result = await api_client.fetch_devices()

        assert result == []
        mock_client.fetch_devices.assert_called_once()

    async def test_fetch_pids_success(self, api_client, mock_client):
        """Test fetching PIDs successfully."""
        mock_client.fetch_pids.return_value = {
            "code": 1,
            "data": {"light": "pid1,pid2", "sensor": "pid3,pid4"},
        }

        result = await api_client.fetch_pids()

        assert isinstance(result, dict)
        assert result["light"] == "pid1,pid2"
        assert result["sensor"] == "pid3,pid4"
        mock_client.fetch_pids.assert_called_once()

    async def test_fetch_device_statuses_success(self, api_client, mock_client):
        """Test fetching device statuses successfully."""
        mock_client.fetch_device_statuses.return_value = {
            "code": 1,
            "data": [{"deviceName": "device1", "temp": 22.5, "humi": 65.0}],
        }

        result = await api_client.fetch_device_statuses()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["temp"] == 22.5
        mock_client.fetch_device_statuses.assert_called_once()

    async def test_filter_sensor_devices(self, api_client):
        """Test filtering sensor devices."""
        devices = [
            {"deviceName": "sensor1", "deviceMoldPid": "pid1"},
            {"deviceName": "light1", "deviceMoldPid": "pid2"},
            {"deviceName": "sensor2", "deviceMoldPid": "pid3"},
        ]
        pids = {"sensor": "pid1, pid3", "light": "pid2"}

        result = api_client.filter_sensor_devices(devices, pids)

        assert len(result) == 2
        assert result[0]["deviceName"] == "sensor1"
        assert result[1]["deviceName"] == "sensor2"

    async def test_merge_device_status(self, api_client):
        """Test merging device info with status."""
        devices = [
            {"deviceName": "device1", "deviceId": "id1"},
            {"deviceName": "device2", "deviceId": "id2"},
        ]
        statuses = [
            {"deviceName": "device1", "temp": 22.5, "humi": 65.0},
        ]

        result = api_client.merge_device_status(devices, statuses)

        assert len(result) == 2
        assert result[0]["temp"] == 22.5
        assert result[0]["humi"] == 65.0
        assert "temp" not in result[1]

    async def test_close(self, api_client, mock_client):
        """Test closing the API client."""
        await api_client.close()

        mock_client.close.assert_called_once()

    async def test_api_without_client(self):
        """Test API when DayBetter client is not available."""
        with patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterClient",
            None,
        ):
            api = DayBetterApi(token="test_token")
            devices = await api.fetch_devices()
            assert devices == []
