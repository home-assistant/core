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
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

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
    mock_get_clientsession.assert_called_once_with(hass, True)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    mock_karakeep_client.async_get_stats.assert_awaited_once()


@pytest.mark.parametrize(
    "side_effect",
    [
        KarakeepAuthError("Invalid token", 401),
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


async def test_setup_entry_version_failure(
    hass: HomeAssistant,
    mock_karakeep_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when the version fetch fails."""
    mock_karakeep_client.async_get_version.side_effect = KarakeepConnectionError(
        "Cannot connect"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_version_unavailable(
    hass: HomeAssistant,
    mock_karakeep_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test setup succeeds without a version when the endpoint is unavailable."""
    mock_karakeep_client.async_get_version.return_value = None

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert device_entry is not None
    assert device_entry.sw_version is None


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
