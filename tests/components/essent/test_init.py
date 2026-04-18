"""Tests for Essent integration setup."""

from unittest.mock import AsyncMock

from essent_dynamic_pricing import (
    EssentConnectionError,
    EssentDataError,
    EssentError,
    EssentResponseError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.essent.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_essent_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_device_registry(
    hass: HomeAssistant,
    mock_essent_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device is registered correctly."""
    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert device_entry is not None
    assert device_entry == snapshot


@pytest.mark.parametrize(
    "exception",
    [
        EssentConnectionError("fail"),
        EssentResponseError("bad"),
        EssentDataError("bad"),
        EssentError("boom"),
    ],
)
async def test_setup_retry_on_error(
    hass: HomeAssistant,
    mock_essent_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test setup retries on client errors."""
    mock_essent_client.async_get_prices.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
