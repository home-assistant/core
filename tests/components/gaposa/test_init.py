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
    assert init_integration.runtime_data is not None

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_unload_closes_gaposa_client(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_gaposa_instance: MagicMock,
) -> None:
    """Unloading the entry should close the Gaposa session."""
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    mock_gaposa_instance.close.assert_called_once()


async def test_network_failure_during_setup_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gaposa_instance: MagicMock,
    mock_gaposa: MagicMock,
) -> None:
    """If the first refresh fails with a network error the entry enters SETUP_RETRY."""
    mock_gaposa_instance.update.side_effect = OSError("boom")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "exc",
    [GaposaAuthException, FirebaseAuthException],
)
async def test_auth_failure_during_setup_triggers_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gaposa_instance: MagicMock,
    mock_gaposa: MagicMock,
    exc: type[Exception],
) -> None:
    """An auth failure during the first refresh triggers reauth via SETUP_ERROR."""
    mock_gaposa_instance.update.side_effect = exc("credentials rejected")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # ConfigEntryAuthFailed during first refresh lands the entry in
    # SETUP_ERROR and queues a reauth flow.
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress_by_handler("gaposa")
    assert any(flow["context"].get("source") == "reauth" for flow in flows)
