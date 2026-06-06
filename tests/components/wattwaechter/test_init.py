"""Tests for the WattWächter Plus integration setup."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from aio_wattwaechter import (
    WattwaechterAuthenticationError,
    WattwaechterConnectionError,
    WattwaechterNoDataError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test successful integration setup and unload."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test setup when device is unreachable."""
    mock_client.alive.side_effect = WattwaechterConnectionError("Connection refused")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("side_effect", WattwaechterNoDataError("No data")),
        ("side_effect", WattwaechterAuthenticationError("Invalid token")),
        ("return_value", None),
    ],
    ids=["no_data", "auth_error", "returns_none"],
)
async def test_setup_entry_retries_on_meter_data_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    attribute: str,
    value: Any,
) -> None:
    """Test setup retries when meter_data fails or returns no data."""
    setattr(mock_client.meter_data, attribute, value)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
