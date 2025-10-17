"""Test the DayBetter API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.daybetter_services.daybetter_api import DayBetterApi


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    return hass


@pytest.fixture
def api_client(mock_hass):
    """Create an API client instance."""
    return DayBetterApi(mock_hass, "test_token_12345")


class TestDayBetterApi:
    """Test the DayBetter API client."""

    @pytest.mark.asyncio
    async def test_fetch_devices_success(self, api_client, mock_hass):
        """Test successful device fetching."""
        mock_devices = [
            {"id": "device1", "name": "Light 1"},
            {"id": "device2", "name": "Switch 1"},
        ]

        with patch(
            "homeassistant.components.daybetter_services.daybetter_api.async_get_clientsession"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session

            # Mock successful response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"data": mock_devices})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session.post.return_value = mock_response

            result = await api_client.fetch_devices()

            assert result == mock_devices
            mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_devices_failure(self, api_client, mock_hass):
        """Test device fetching failure."""
        with patch(
            "homeassistant.components.daybetter_services.daybetter_api.async_get_clientsession"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session

            # Mock failed response
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value="Bad Request")
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session.post.return_value = mock_response

            result = await api_client.fetch_devices()

            assert result == []

    @pytest.mark.asyncio
    async def test_fetch_devices_exception(self, api_client, mock_hass):
        """Test device fetching with exception."""
        with patch(
            "homeassistant.components.daybetter_services.daybetter_api.async_get_clientsession"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session

            # Mock exception
            mock_session.post.side_effect = Exception("Network error")

            result = await api_client.fetch_devices()

            assert result == []

    @pytest.mark.asyncio
    async def test_fetch_pids_success(self, api_client, mock_hass):
        """Test successful PIDs fetching."""
        mock_pids = {"light": ["pid1", "pid2"], "switch": ["pid3", "pid4"]}

        with patch(
            "homeassistant.components.daybetter_services.daybetter_api.async_get_clientsession"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session

            # Mock successful response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"data": mock_pids})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session.post.return_value = mock_response

            result = await api_client.fetch_pids()

            assert result == mock_pids

    @pytest.mark.asyncio
    async def test_control_device_switch(self, api_client, mock_hass):
        """Test device control for switch."""
        with patch(
            "homeassistant.components.daybetter_services.daybetter_api.async_get_clientsession"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session

            # Mock response
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value={"code": 1})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session.post.return_value = mock_response

            result = await api_client.control_device(
                device_name="test_device",
                action=True,
                brightness=None,
                hs_color=None,
                color_temp=None,
            )

            assert result == {"code": 1}

            # Verify correct payload was sent
            call_args = mock_session.post.call_args
            assert call_args[1]["json"]["deviceName"] == "test_device"
            assert call_args[1]["json"]["type"] == 1
            assert call_args[1]["json"]["on"] is True

    @pytest.mark.asyncio
    async def test_control_device_brightness(self, api_client, mock_hass):
        """Test device control for brightness."""
        with patch(
            "homeassistant.components.daybetter_services.daybetter_api.async_get_clientsession"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session

            # Mock response
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value={"code": 1})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session.post.return_value = mock_response

            result = await api_client.control_device(
                device_name="test_device",
                action=None,
                brightness=128,
                hs_color=None,
                color_temp=None,
            )

            assert result == {"code": 1}

            # Verify correct payload was sent
            call_args = mock_session.post.call_args
            assert call_args[1]["json"]["deviceName"] == "test_device"
            assert call_args[1]["json"]["type"] == 2
            assert call_args[1]["json"]["brightness"] == 128

    @pytest.mark.asyncio
    async def test_control_device_color(self, api_client, mock_hass):
        """Test device control for color."""
        with patch(
            "homeassistant.components.daybetter_services.daybetter_api.async_get_clientsession"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session

            # Mock response
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value={"code": 1})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session.post.return_value = mock_response

            result = await api_client.control_device(
                device_name="test_device",
                action=None,
                brightness=255,
                hs_color=(180.0, 50.0),
                color_temp=None,
            )

            assert result == {"code": 1}

            # Verify correct payload was sent
            call_args = mock_session.post.call_args
            assert call_args[1]["json"]["deviceName"] == "test_device"
            assert call_args[1]["json"]["type"] == 3
            assert call_args[1]["json"]["hue"] == 180.0
            assert call_args[1]["json"]["saturation"] == 0.5
            assert call_args[1]["json"]["brightness"] == 1.0

    @pytest.mark.asyncio
    async def test_control_device_color_temp(self, api_client, mock_hass):
        """Test device control for color temperature."""
        with patch(
            "homeassistant.components.daybetter_services.daybetter_api.async_get_clientsession"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session

            # Mock response
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value={"code": 1})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session.post.return_value = mock_response

            result = await api_client.control_device(
                device_name="test_device",
                action=None,
                brightness=None,
                hs_color=None,
                color_temp=4000,
            )

            assert result == {"code": 1}

            # Verify correct payload was sent
            call_args = mock_session.post.call_args
            assert call_args[1]["json"]["deviceName"] == "test_device"
            assert call_args[1]["json"]["type"] == 4
            assert call_args[1]["json"]["kelvin"] == 250  # 1000000 / 4000

    @pytest.mark.asyncio
    async def test_fetch_mqtt_config_success(self, api_client, mock_hass):
        """Test successful MQTT config fetching."""
        mock_config = {
            "host": "mqtt.example.com",
            "port": 8883,
            "username": "test_user",
        }

        with patch(
            "homeassistant.components.daybetter_services.daybetter_api.async_get_clientsession"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session

            # Mock successful response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"data": mock_config})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session.post.return_value = mock_response

            result = await api_client.fetch_mqtt_config()

            assert result == mock_config

    @pytest.mark.asyncio
    async def test_fetch_mqtt_config_failure(self, api_client, mock_hass):
        """Test MQTT config fetching failure."""
        with patch(
            "homeassistant.components.daybetter_services.daybetter_api.async_get_clientsession"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session

            # Mock failed response
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value="Bad Request")
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session.post.return_value = mock_response

            result = await api_client.fetch_mqtt_config()

            assert result == {}
