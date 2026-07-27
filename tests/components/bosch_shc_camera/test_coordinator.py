"""Tests for coordinator.py's pure helper functions."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.components.bosch_shc_camera.coordinator import get_options
from homeassistant.components.bosch_shc_camera.tick_housekeeping import run_housekeeping

from tests.common import MockConfigEntry


def test_get_options_ignores_legacy_polling_keys() -> None:
    """A HACS-migrated entry's stale polling keys must not override defaults.

    scan_interval/interval_status/interval_events/snapshot_interval values
    must never override the fixed DEFAULT_OPTIONS cadence — their
    options-flow fields were removed for Bronze's appropriate-polling rule,
    but the entry data can still carry them under the same key names
    (bug-hunt 2026-07-27, Copilot review round 3).
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={},
        options={
            "scan_interval": 5,
            "interval_status": 5,
            "interval_events": 5,
            "snapshot_interval": 5,
            "enable_snapshots": False,
        },
    )
    opts = get_options(entry)
    assert opts["scan_interval"] == 60
    assert opts["interval_status"] == 300
    assert opts["interval_events"] == 300
    assert opts["snapshot_interval"] == 1800
    # Non-polling options still merge normally.
    assert opts["enable_snapshots"] is False


def test_get_options_defaults_when_entry_has_no_options() -> None:
    """A fresh entry with no options at all gets the plain defaults."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={}, options={})
    opts = get_options(entry)
    assert opts["scan_interval"] == 60
    assert opts["enable_snapshots"] is True


async def test_housekeeping_runs_stale_cleanup_for_definitive_empty_camera_list() -> (
    None
):
    """The last camera being removed (data == {}) must still run cleanup.

    `fetch_camera_list` already raises on any fetch failure before
    housekeeping ever runs, so an empty `data` here is a genuine
    zero-camera account, not a glitch (bug-hunt 2026-07-27, Copilot review
    round 3).
    """
    coordinator = SimpleNamespace(cleanup_stale_devices=MagicMock())
    await run_housekeeping(coordinator, {}, {}, now=0.0, is_first_tick=False)
    coordinator.cleanup_stale_devices.assert_called_once_with(set())


async def test_housekeeping_skips_cleanup_on_first_tick() -> None:
    """The fast first tick must not run cleanup.

    It would race device registration in async_setup_entry.
    """
    coordinator = SimpleNamespace(cleanup_stale_devices=MagicMock())
    await run_housekeeping(coordinator, {}, {}, now=0.0, is_first_tick=True)
    coordinator.cleanup_stale_devices.assert_not_called()


async def test_housekeeping_persists_empty_credential_snapshot_on_last_camera_removed() -> (
    None
):
    """Clearing the last camera's creds must still persist the empty snapshot.

    Otherwise a deleted camera's Digest credentials remain in `.storage`
    indefinitely (bug-hunt 2026-07-27, Copilot review round 3).
    """
    store = MagicMock()
    store.async_save = MagicMock(return_value=None)
    coordinator = SimpleNamespace(
        cleanup_stale_devices=MagicMock(),
        local_creds_store=store,
        local_creds_cache={},
        local_creds_snapshot={"OLD-CAM": {"user": "u", "password": "p", "host": "h"}},
        spawn_tracked=MagicMock(),
    )
    await run_housekeeping(coordinator, {}, {}, now=0.0, is_first_tick=False)
    assert coordinator.local_creds_snapshot == {}
    coordinator.spawn_tracked.assert_called_once()
