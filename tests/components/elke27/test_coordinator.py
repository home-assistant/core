"""Tests for the Elke27 data update coordinator."""

import asyncio
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

from elke27_lib.errors import Elke27ConnectionError
import pytest

from homeassistant.components.elke27 import coordinator as coordinator_module
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import (
    connection_state_changed_event,
    domain_csm_changed_event,
    setup_integration,
    table_csm_changed_event,
)

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "event_factory",
    [
        pytest.param(domain_csm_changed_event, id="domain-csm"),
        pytest.param(table_csm_changed_event, id="table-csm"),
    ],
)
async def test_csm_change_refreshes_domain_config(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    event_factory: Callable[[str], Any],
) -> None:
    """Test CSM change events trigger a debounced domain config refresh."""
    monkeypatch.setattr(coordinator_module, "_DEBOUNCE_SECONDS", 0)
    await setup_integration(hass, mock_config_entry)

    mock_client.event_callback(event_factory("zone"))
    await hass.async_block_till_done()

    mock_client.async_refresh_domain_config.assert_awaited_once_with("zone")


async def test_domain_refresh_errors_are_deferred(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test connection errors during a domain refresh are not raised."""
    monkeypatch.setattr(coordinator_module, "_DEBOUNCE_SECONDS", 0)
    await setup_integration(hass, mock_config_entry)
    mock_client.async_refresh_domain_config.side_effect = Elke27ConnectionError()

    mock_client.event_callback(domain_csm_changed_event("zone"))
    await hass.async_block_till_done()

    mock_client.async_refresh_domain_config.assert_awaited_once_with("zone")


async def test_reconnect_triggers_full_refresh(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a reconnect event triggers a full CSM refresh."""
    await setup_integration(hass, mock_config_entry)
    assert mock_client.async_refresh_csm.await_count == 1

    mock_client.connection_callback(connection_state_changed_event(connected=True))
    await hass.async_block_till_done()

    assert mock_client.async_refresh_csm.await_count == 2


async def test_unload_cancels_pending_domain_refresh(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading cancels a pending debounced domain refresh."""
    await setup_integration(hass, mock_config_entry)

    mock_client.event_callback(domain_csm_changed_event("zone"))
    await asyncio.sleep(0)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_client.async_refresh_domain_config.assert_not_awaited()
    mock_client.async_disconnect.assert_awaited_once()
