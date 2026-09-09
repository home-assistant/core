"""Tests for the Bitvis Power Hub coordinator."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import FakeListener

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("patch_shared_listener")


async def test_setup_oserror_results_in_setup_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_shared_listener: FakeListener,
) -> None:
    """Test that OSError from SharedListener.start results in SETUP_RETRY."""
    mock_shared_listener.start = AsyncMock(side_effect=OSError("port in use"))
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_runtime_error_results_in_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_shared_listener: FakeListener,
) -> None:
    """Test that RuntimeError from SharedListener.register results in SETUP_ERROR."""
    mock_shared_listener.register.side_effect = RuntimeError("duplicate filter")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_shared_listener.unregister.assert_not_called()
