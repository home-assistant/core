"""Test OTBR Silicon Labs Multiprotocol support."""
from unittest.mock import patch

import pytest
from python_otbr_api import ActiveDataSet

from homeassistant.components import otbr
from homeassistant.components.otbr import (
    silabs_multiprotocol as otbr_silabs_multiprotocol,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

OTBR_MULTIPAN_URL = "http://core-silabs-multiprotocol:8081"
OTBR_NON_MULTIPAN_URL = "/dev/ttyAMA1"


async def test_async_change_channel(hass: HomeAssistant, otbr_config_entry) -> None:
    """Test test_async_change_channel."""

    with patch("python_otbr_api.OTBR.set_channel") as mock_set_channel:
        await otbr_silabs_multiprotocol.async_change_channel(hass, 16)
    mock_set_channel.assert_awaited_once_with(16)


async def test_async_change_channel_no_otbr(hass: HomeAssistant) -> None:
    """Test async_change_channel when otbr is not configured."""

    with patch("python_otbr_api.OTBR.set_channel") as mock_set_channel:
        await otbr_silabs_multiprotocol.async_change_channel(hass, 16)
    mock_set_channel.assert_not_awaited()


async def test_async_get_channel(hass: HomeAssistant, otbr_config_entry) -> None:
    """Test test_async_get_channel."""

    with patch(
        "python_otbr_api.OTBR.get_active_dataset",
        return_value=ActiveDataSet(channel=11),
    ) as mock_get_active_dataset:
        assert await otbr_silabs_multiprotocol.async_get_channel(hass) == 11
    mock_get_active_dataset.assert_awaited_once_with()


async def test_async_get_channel_no_dataset(
    hass: HomeAssistant, otbr_config_entry
) -> None:
    """Test test_async_get_channel."""

    with patch(
        "python_otbr_api.OTBR.get_active_dataset",
        return_value=None,
    ) as mock_get_active_dataset:
        assert await otbr_silabs_multiprotocol.async_get_channel(hass) is None
    mock_get_active_dataset.assert_awaited_once_with()


async def test_async_get_channel_error(hass: HomeAssistant, otbr_config_entry) -> None:
    """Test test_async_get_channel."""

    with patch(
        "python_otbr_api.OTBR.get_active_dataset",
        side_effect=HomeAssistantError,
    ) as mock_get_active_dataset:
        assert await otbr_silabs_multiprotocol.async_get_channel(hass) is None
    mock_get_active_dataset.assert_awaited_once_with()


async def test_async_get_channel_no_otbr(hass: HomeAssistant) -> None:
    """Test test_async_get_channel when otbr is not configured."""

    with patch("python_otbr_api.OTBR.get_active_dataset") as mock_get_active_dataset:
        await otbr_silabs_multiprotocol.async_get_channel(hass)
    mock_get_active_dataset.assert_not_awaited()


@pytest.mark.parametrize(
    ("url", "expected"),
    [(OTBR_MULTIPAN_URL, True), (OTBR_NON_MULTIPAN_URL, False)],
)
async def test_async_using_multipan(
    hass: HomeAssistant, otbr_config_entry, url: str, expected: bool
) -> None:
    """Test async_change_channel when otbr is not configured."""
    data: otbr.OTBRData = hass.data[otbr.DOMAIN]
    data.url = url

    assert await otbr_silabs_multiprotocol.async_using_multipan(hass) is expected


async def test_async_using_multipan_no_otbr(hass: HomeAssistant) -> None:
    """Test async_change_channel when otbr is not configured."""

    assert await otbr_silabs_multiprotocol.async_using_multipan(hass) is False
