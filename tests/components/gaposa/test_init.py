"""Test setup and teardown of the Gaposa integration."""

from __future__ import annotations

from unittest.mock import MagicMock

from pygaposa import FirebaseAuthException, GaposaAuthException
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Happy path: integration sets up, entry is LOADED, unload works cleanly."""
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_unload_closes_gaposa_client(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_gaposa: MagicMock,
) -> None:
    """Unloading the entry should close the Gaposa session."""
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    mock_gaposa.close.assert_called_once()


@pytest.mark.parametrize(
    ("target", "exc"),
    [
        ("update", OSError("boom")),
        ("login", OSError("cloud unreachable")),
        ("update", GaposaAuthException("credentials rejected")),
        ("update", FirebaseAuthException("credentials rejected")),
    ],
)
async def test_setup_failure_retries_and_closes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gaposa: MagicMock,
    target: str,
    exc: Exception,
) -> None:
    """Any failure during setup enters SETUP_RETRY and releases the client."""
    getattr(mock_gaposa, target).side_effect = exc

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_gaposa.close.assert_called_once()
