"""Tests for Papouch utils."""

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from homeassistant.components.papouch.utils import _get_device_name


async def test_get_device_name_error() -> None:
    """Test fallback name on connection error."""
    with patch("homeassistant.components.papouch.utils.PapouchHTTPClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.get_device_info = AsyncMock(side_effect=aiohttp.ClientError())
        mock_session = AsyncMock()

        name = await _get_device_name(mock_session, "192.168.1.50")
        assert name == "Papouch Device - (NONAME)"


@pytest.mark.parametrize(
    ("get_device_info_return_value", "expected_state"),
    [
        ((None, None), "Papouch Device - (NONAME)"),
        (("Quido", None), "Quido (NONAME)"),
        ((None, "Garden"), "Papouch device (Garden)"),
        (("Quido", "Workshop"), "Quido (Workshop)"),
    ],
)
async def test_get_device_name(get_device_info_return_value, expected_state) -> None:
    """Test get_device_info with various responses of get_device_info."""

    with patch("homeassistant.components.papouch.utils.PapouchHTTPClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.get_device_info = AsyncMock(
            return_value=get_device_info_return_value
        )

        mock_session = AsyncMock()
        name = await _get_device_name(mock_session, "192.168.1.50")
        assert name == expected_state
