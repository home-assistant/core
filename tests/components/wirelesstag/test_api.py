"""Test the Wireless Sensor Tag API wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.components.wirelesstag.api import WirelessTagAPI
from homeassistant.core import HomeAssistant

from . import MOCK_TAGS


@pytest.fixture
def mock_wirelesstag_api_raw() -> MagicMock:
    """Mock wirelesstagpy API."""
    # Create a mock with a spec that only includes known methods
    mock_api = Mock(spec=["load_tags", "arm_motion", "disarm_motion"])
    mock_api.load_tags.return_value = MOCK_TAGS
    mock_api.arm_motion.return_value = True
    mock_api.disarm_motion.return_value = True
    return mock_api


async def test_authenticate_success(
    hass: HomeAssistant, mock_wirelesstag_api_raw: MagicMock
) -> None:
    """Test successful authentication."""
    with patch(
        "homeassistant.components.wirelesstag.api.WirelessTags",
        return_value=mock_wirelesstag_api_raw,
    ):
        api = WirelessTagAPI(hass, "test@example.com", "password123")
        result = await api.async_authenticate()
        assert result is True


async def test_authenticate_failure(hass: HomeAssistant) -> None:
    """Test authentication failure."""
    with patch(
        "homeassistant.components.wirelesstag.api.WirelessTags",
        side_effect=Exception("Authentication failed"),
    ):
        api = WirelessTagAPI(hass, "invalid@example.com", "wrongpass")
        result = await api.async_authenticate()
        assert result is False


async def test_get_tags(
    hass: HomeAssistant, mock_wirelesstag_api_raw: MagicMock
) -> None:
    """Test getting tags."""
    with patch(
        "homeassistant.components.wirelesstag.api.WirelessTags",
        return_value=mock_wirelesstag_api_raw,
    ):
        api = WirelessTagAPI(hass, "test@example.com", "password123")
        await api.async_authenticate()
        tags = await api.async_get_tags()
        assert len(tags) == 2
        assert "tag1" in tags
        assert "tag2" in tags
        assert tags["tag1"]["name"] == "Living Room"
        assert tags["tag2"]["name"] == "Bedroom"


async def test_arm_tag(
    hass: HomeAssistant, mock_wirelesstag_api_raw: MagicMock
) -> None:
    """Test arming a tag."""
    with patch(
        "homeassistant.components.wirelesstag.api.WirelessTags",
        return_value=mock_wirelesstag_api_raw,
    ):
        api = WirelessTagAPI(hass, "test@example.com", "password123")
        await api.async_authenticate()
        result = await api.async_arm_tag("tag1", "00:11:22:33:44:55", "motion")
        assert result is True
        mock_wirelesstag_api_raw.arm_motion.assert_called_once_with(
            "tag1", "00:11:22:33:44:55"
        )


async def test_disarm_tag(
    hass: HomeAssistant, mock_wirelesstag_api_raw: MagicMock
) -> None:
    """Test disarming a tag."""
    with patch(
        "homeassistant.components.wirelesstag.api.WirelessTags",
        return_value=mock_wirelesstag_api_raw,
    ):
        api = WirelessTagAPI(hass, "test@example.com", "password123")
        await api.async_authenticate()
        result = await api.async_disarm_tag("tag1", "00:11:22:33:44:55", "motion")
        assert result is True
        mock_wirelesstag_api_raw.disarm_motion.assert_called_once_with(
            "tag1", "00:11:22:33:44:55"
        )


async def test_arm_tag_unknown_sensor_type(
    hass: HomeAssistant, mock_wirelesstag_api_raw: MagicMock
) -> None:
    """Test arming a tag with unknown sensor type."""
    with patch(
        "homeassistant.components.wirelesstag.api.WirelessTags",
        return_value=mock_wirelesstag_api_raw,
    ):
        api = WirelessTagAPI(hass, "test@example.com", "password123")
        await api.async_authenticate()
        result = await api.async_arm_tag("tag1", "00:11:22:33:44:55", "unknown")
        assert result is False


async def test_disarm_tag_unknown_sensor_type(
    hass: HomeAssistant, mock_wirelesstag_api_raw: MagicMock
) -> None:
    """Test disarming a tag with unknown sensor type."""
    with patch(
        "homeassistant.components.wirelesstag.api.WirelessTags",
        return_value=mock_wirelesstag_api_raw,
    ):
        api = WirelessTagAPI(hass, "test@example.com", "password123")
        await api.async_authenticate()
        result = await api.async_disarm_tag("tag1", "00:11:22:33:44:55", "unknown")
        assert result is False
