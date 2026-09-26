"""Tests for Papouch utils."""

from unittest.mock import AsyncMock, patch

import aiohttp

from homeassistant.components.papouch.utils import _get_device_name
from homeassistant.core import HomeAssistant


async def test_get_device_name_success(hass: HomeAssistant) -> None:
    """Test getting device name successfully."""
    with patch("homeassistant.components.papouch.utils.PapouchHTTPClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.get_device_info = AsyncMock(return_value=("Quido", "Lab"))

        name = await _get_device_name(hass, "192.168.1.50")
        assert name == "Quido (Lab)"


async def test_get_device_name_error(hass: HomeAssistant) -> None:
    """Test fallback name on connection error."""
    with patch("homeassistant.components.papouch.utils.PapouchHTTPClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.get_device_info = AsyncMock(side_effect=aiohttp.ClientError())

        name = await _get_device_name(hass, "192.168.1.50")
        assert name == "Papouch Device"


async def test_get_device_name_empty(hass: HomeAssistant) -> None:
    """Test fallback name on empty info."""
    with patch("homeassistant.components.papouch.utils.PapouchHTTPClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.get_device_info = AsyncMock(return_value=(None, None))

        name = await _get_device_name(hass, "192.168.1.50")
        assert name == "Papouch Device"
