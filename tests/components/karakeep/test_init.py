"""Tests for the Karakeep integration setup."""

from unittest.mock import AsyncMock, patch

from aiokarakeep import (
    KarakeepApiError,
    KarakeepAuthError,
    KarakeepConnectionError,
    KarakeepInvalidResponseError,
)
import pytest

from homeassistant.components.karakeep.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_karakeep_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up the integration."""
    with patch(
        "homeassistant.components.karakeep.async_get_clientsession"
    ) as mock_get_clientsession:
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_get_clientsession.assert_called_once_with(hass, False)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    mock_karakeep_client.async_get_stats.assert_awaited_once()


async def test_setup_entry_auth_failure(
    hass: HomeAssistant,
    mock_karakeep_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails on authentication errors."""
    mock_karakeep_client.async_get_stats.side_effect = KarakeepAuthError(
        "Invalid token",
        401,
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = list(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.parametrize(
    "side_effect",
    [
        KarakeepConnectionError("Cannot connect"),
        KarakeepApiError("API error", 500),
        KarakeepInvalidResponseError("Invalid response"),
    ],
)
async def test_setup_entry_update_failure(
    hass: HomeAssistant,
    mock_karakeep_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test setup retries on update failures."""
    mock_karakeep_client.async_get_stats.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_karakeep_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
