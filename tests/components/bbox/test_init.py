"""Tests for Bbox init."""

from unittest.mock import AsyncMock

from aiobbox import BboxApiError, BboxAuthError
import pytest

from homeassistant.components.bbox.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_unload_entry(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading the config entry."""
    await setup_integration(hass, mock_config_entry)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


@pytest.mark.parametrize(
    "side_effect",
    [
        BboxAuthError("Authentication failed"),
        BboxApiError("API error"),
        Exception("Unexpected error"),
    ],
)
async def test_setup_entry_failure(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test setup entry failure."""
    mock_bbox_api.authenticate.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_auth_failure(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup entry with authentication failure."""
    mock_bbox_api.authenticate.side_effect = BboxAuthError("Invalid credentials")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_api_failure(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup entry with API failure."""
    mock_bbox_api.get_router_info.side_effect = BboxApiError("API error")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
