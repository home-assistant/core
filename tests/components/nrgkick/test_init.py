"""Tests for the NRGkick integration initialization."""

from __future__ import annotations

from unittest.mock import AsyncMock

from nrgkick_api import (
    NRGkickAPIDisabledError,
    NRGkickAuthenticationError,
    NRGkickConnectionError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nrgkick.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test successful load and unload of entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (NRGkickAuthenticationError, ConfigEntryState.SETUP_ERROR),
        (NRGkickAPIDisabledError, ConfigEntryState.SETUP_ERROR),
        (NRGkickConnectionError, ConfigEntryState.SETUP_RETRY),
        (TimeoutError, ConfigEntryState.SETUP_RETRY),
        (OSError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_entry_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test setup entry with failed connection."""
    mock_nrgkick_api.get_info.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state


async def test_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test successful load and unload of entry."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device is not None
    assert device == snapshot
