"""Tests for FritzBox VPN runtime model helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.components.fritzbox_vpn.models import (
    FritzboxVpnRuntimeData,
    runtime_from_entry,
    runtime_from_hass,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _runtime() -> FritzboxVpnRuntimeData:
    """Create a minimal runtime data instance."""
    coordinator = MagicMock()
    return FritzboxVpnRuntimeData(coordinator=coordinator)


def test_platform_tracking_returns_switch_set_and_lock() -> None:
    """platform_tracking returns correct set/lock for switch platform."""
    runtime = _runtime()
    runtime.known_uids_switch = {"uid-1"}

    known_uids, lock = runtime.platform_tracking(platform="switch")  # type: ignore[arg-type]
    assert known_uids is runtime.known_uids_switch
    assert lock is runtime.lock_add_entities_switch


def test_clear_known_uids_removes_uids_but_keeps_others() -> None:
    """clear_known_uids removes only the given UIDs."""
    runtime = _runtime()
    runtime.known_uids_switch = {"a", "b"}

    runtime.clear_known_uids({"a"})
    assert runtime.known_uids_switch == {"b"}


def test_clear_known_uids_noop_on_empty_set() -> None:
    """clear_known_uids with empty set is a no-op."""
    runtime = _runtime()
    runtime.known_uids_switch = {"a"}

    runtime.clear_known_uids(set())
    assert runtime.known_uids_switch == {"a"}


def test_runtime_from_entry_returns_typed_instance() -> None:
    """runtime_from_entry returns runtime data for typed entries only."""
    entry: MockConfigEntry = MockConfigEntry(domain="fritzbox_vpn", data={})
    entry.runtime_data = _runtime()

    runtime = runtime_from_entry(entry)
    assert runtime is not None
    assert isinstance(runtime, FritzboxVpnRuntimeData)


def test_runtime_from_entry_returns_none_when_wrong_type() -> None:
    """runtime_from_entry returns None when entry.runtime_data is not typed."""
    entry: MockConfigEntry = MockConfigEntry(domain="fritzbox_vpn", data={})
    entry.runtime_data = object()

    runtime = runtime_from_entry(entry)
    assert runtime is None


@pytest.mark.asyncio
async def test_runtime_from_hass_requires_loaded_state(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """runtime_from_hass only returns runtime when config entry is loaded."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _runtime()
    mock_config_entry.mock_state(hass, ConfigEntryState.NOT_LOADED)

    assert runtime_from_hass(hass, mock_config_entry.entry_id) is None

    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    assert runtime_from_hass(hass, mock_config_entry.entry_id) is not None
