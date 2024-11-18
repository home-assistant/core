"""Test the Aquacell init module."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

from aioaquacell import AquacellApiException, AuthenticationFailed
import pytest

from homeassistant.components.aquacell.const import (
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_CREATION_TIME,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_aquacell_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_load_withoutbrand(
    hass: HomeAssistant,
    mock_aquacell_api: AsyncMock,
    mock_config_entry_without_brand: MockConfigEntry,
) -> None:
    """Test load entry without brand."""
    await setup_integration(hass, mock_config_entry_without_brand)

    assert mock_config_entry_without_brand.state is ConfigEntryState.LOADED


async def test_coordinator_update_valid_refresh_token(
    hass: HomeAssistant,
    mock_aquacell_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state is ConfigEntryState.LOADED

    assert len(mock_aquacell_api.authenticate.mock_calls) == 0
    assert len(mock_aquacell_api.authenticate_refresh.mock_calls) == 1
    assert len(mock_aquacell_api.get_all_softeners.mock_calls) == 1


async def test_coordinator_update_expired_refresh_token(
    hass: HomeAssistant,
    mock_aquacell_api: AsyncMock,
    mock_config_entry_expired: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    mock_aquacell_api.authenticate.return_value = "new-refresh-token"

    now = datetime.now()
    with patch(
        "homeassistant.components.aquacell.coordinator.datetime"
    ) as datetime_mock:
        datetime_mock.now.return_value = now
        await setup_integration(hass, mock_config_entry_expired)

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state is ConfigEntryState.LOADED

    assert len(mock_aquacell_api.authenticate.mock_calls) == 1
    assert len(mock_aquacell_api.authenticate_refresh.mock_calls) == 0
    assert len(mock_aquacell_api.get_all_softeners.mock_calls) == 1

    assert entry.data[CONF_REFRESH_TOKEN] == "new-refresh-token"
    assert entry.data[CONF_REFRESH_TOKEN_CREATION_TIME] == now.timestamp()


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (AuthenticationFailed, ConfigEntryState.SETUP_ERROR),
        (AquacellApiException, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_load_exceptions(
    hass: HomeAssistant,
    mock_aquacell_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test load and unload entry."""
    mock_aquacell_api.authenticate_refresh.side_effect = exception
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state is expected_state
