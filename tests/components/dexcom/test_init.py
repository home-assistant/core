"""Test the Dexcom config flow."""

from collections.abc import Generator
from unittest.mock import MagicMock

from pydexcom.errors import (
    AccountError,
    AccountErrorEnum,
    ServerError,
    ServerErrorEnum,
    SessionError,
    SessionErrorEnum,
)
import pytest

from homeassistant.components.dexcom.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import init_integration

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_dexcom: MagicMock
) -> None:
    """Test successful setup of entry."""
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "error",
    [
        AccountError(AccountErrorEnum.FAILED_AUTHENTICATION),
        Exception,
    ],
)
async def test_setup_entry_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dexcom_gen: Generator[MagicMock],
    error: Exception | None,
) -> None:
    """Test we handle setup entry errors."""
    mock_dexcom_gen.side_effect = error
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "error",
    [
        SessionError(SessionErrorEnum.INVALID),
        ServerError(ServerErrorEnum.UNEXPECTED),
    ],
)
async def test_setup_entry_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dexcom_gen: Generator[MagicMock],
    error: Exception | None,
) -> None:
    """Test we handle setup entry retry-able errors."""
    mock_dexcom_gen.side_effect = error
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_dexcom: MagicMock
) -> None:
    """Test successful unload of entry."""
    await init_integration(hass, mock_config_entry)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
