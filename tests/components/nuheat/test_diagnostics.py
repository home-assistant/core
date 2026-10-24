"""Diagnostics never serialize account data or perform cloud operations."""

from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from chemelex_nuheat import ScheduleMode
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.nuheat.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .test_integration import coordinator_with, thermostat


@pytest.mark.parametrize("cooldown", [0, 120])
async def test_diagnostics_allowlist_and_no_cloud_calls(
    hass: HomeAssistant, cooldown: int
) -> None:
    """Nested private keys, unknown fields, model data and errors stay local."""
    marker = "synthetic-private-do-not-export"
    coordinator, api, entry = await coordinator_with(hass, thermostat(serial=marker))
    api.cooldown_remaining = cooldown
    token_session = MagicMock()
    entry.runtime_data = SimpleNamespace(
        coordinator=coordinator, api=api, oauth_session=token_session
    )
    hass.config_entries.async_update_entry(
        entry,
        data={marker: {"nested": [{marker: marker}]}},
        options={"private": {marker: marker}},
        title=marker,
        unique_id=marker,
    )
    coordinator.last_exception = RuntimeError(marker)
    coordinator.unknown_vendor_field = {marker: marker}
    coordinator.async_set_pending_mode(marker, ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE)
    coordinator.async_set_pending_setpoint(
        marker, 24, hold_until=datetime(2026, 10, 25, tzinfo=UTC)
    )
    api.reset_mock()
    before = (dict(entry.data), dict(entry.options), entry.unique_id)

    with (
        patch(
            "homeassistant.components.nuheat.diagnostics.version", return_value="0.1.3"
        ),
    ):
        result = await async_get_config_entry_diagnostics(hass, entry)

    assert result == {
        "versions": {"core": HA_VERSION, "sdk": "0.1.3"},
        "entry_state": entry.state.value,
        "runtime": {
            "availability": {
                "last_update_success": True,
                "known_devices": 1,
                "available_devices": 1,
            },
            "cooldown_active": bool(cooldown),
            "confirmation": {
                "pending_targets": 1,
                "pending_modes": 1,
                "pending_expiries": 1,
            },
        },
    }
    assert marker not in json.dumps(result)
    assert not api.mock_calls
    assert not token_session.mock_calls
    assert before == (dict(entry.data), dict(entry.options), entry.unique_id)
    await coordinator.async_shutdown()


async def test_diagnostics_before_setup_and_without_sdk_metadata(
    hass: HomeAssistant,
) -> None:
    """An incomplete entry produces a minimal snapshot without raw errors."""

    entry = MockConfigEntry(
        domain="nuheat",
        data={"token": {"access_token": "synthetic-private-token"}},
        title="synthetic-private-title",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.nuheat.diagnostics.version",
        side_effect=PackageNotFoundError("synthetic-private-path"),
    ):
        result = await async_get_config_entry_diagnostics(hass, entry)
    assert result == {
        "versions": {"core": HA_VERSION, "sdk": None},
        "entry_state": "not_loaded",
        "runtime": None,
    }


async def test_diagnostics_failed_refresh_retains_only_coarse_availability(
    hass: HomeAssistant,
) -> None:
    """Cached offline/failed data does not leak its exception or device fields."""
    coordinator, api, entry = await coordinator_with(hass, thermostat(online=False))
    entry.runtime_data = SimpleNamespace(coordinator=coordinator)
    coordinator.last_update_success = False
    coordinator.last_exception = RuntimeError("synthetic-private-url-and-token")
    api.reset_mock()
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["runtime"]["availability"] == {
        "last_update_success": False,
        "known_devices": 1,
        "available_devices": 0,
    }
    assert "synthetic-private" not in json.dumps(result)
    assert not api.mock_calls
    await coordinator.async_shutdown()


async def test_diagnostics_download_uses_cached_state(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """The standard admin download exposes only local, sanitized integration data."""
    marker = "synthetic-private-download-marker"
    coordinator, api, entry = await coordinator_with(hass, thermostat(serial=marker))
    session = MagicMock()
    entry.runtime_data = SimpleNamespace(coordinator=coordinator, oauth_session=session)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    hass.config_entries.async_update_entry(
        entry,
        data={"token": {"access_token": marker}},
        options={marker: marker},
        title=marker,
        unique_id=marker,
    )
    assert await async_setup_component(hass, "nuheat", {})
    await hass.async_block_till_done()
    api.reset_mock()
    before = (dict(entry.data), dict(entry.options), entry.unique_id)
    with patch(
        "homeassistant.components.nuheat.diagnostics.version", return_value="0.1.3"
    ):
        result = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert result["versions"] == {"core": HA_VERSION, "sdk": "0.1.3"}
    assert result["entry_state"] == "loaded"
    assert marker not in json.dumps(result)
    assert not api.mock_calls
    assert not session.mock_calls
    assert before == (dict(entry.data), dict(entry.options), entry.unique_id)
    await coordinator.async_shutdown()
