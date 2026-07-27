"""Integration tests for config entry setup/unload.

The coordinator's `_async_update_data` is the integration's sole network
boundary (GET /v11/video_inputs et al. against Bosch's cloud) — patched
here instead of mocking aiohttp directly, since cloud_ssl.py builds its own
pinned-TLS ClientSession outside of `async_create_clientsession` and so
isn't reachable via the standard `aioclient_mock` fixture.
"""

from unittest.mock import patch

from homeassistant.components.bosch_shc_camera import async_remove_entry
from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.storage import Store

from tests.common import MockConfigEntry

CAM_ID = "AABBCCDD-1122-3344-5566-778899001122"

FAKE_COORDINATOR_DATA = {
    CAM_ID: {
        "info": {
            "title": "Front Door",
            "hardwareVersion": "HOME_Eyes_Outdoor",
            "firmwareVersion": "9.40.104",
            "macAddress": "aa:bb:cc:dd:ee:ff",
        },
        "status": "ONLINE",
        "events": [],
    }
}


def _mock_config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={
            "bearer_token": "test-bearer-token",
            "refresh_token": "test-refresh-token",
        },
        options={},
    )


async def test_setup_and_unload_entry(hass: HomeAssistant) -> None:
    """A config entry with a mocked coordinator refresh loads a camera entity and unloads cleanly."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    coordinator_path = (
        "homeassistant.components.bosch_shc_camera.coordinator.BoschCameraCoordinator"
    )
    with (
        patch(
            f"{coordinator_path}._async_update_data",
            return_value=FAKE_COORDINATOR_DATA,
        ),
        # The camera entity fires a background snapshot refresh on startup —
        # these are the coordinator's real network-touching snapshot methods,
        # stubbed here so the test never opens a real socket.
        patch(f"{coordinator_path}.async_fetch_live_snapshot", return_value=None),
        patch(f"{coordinator_path}.async_fetch_live_snapshot_local", return_value=None),
        patch(
            f"{coordinator_path}.async_fetch_fresh_event_snapshot", return_value=None
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        state = hass.states.get("camera.bosch_front_door")
        assert state is not None

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.NOT_LOADED
        # Unloading marks the entity unavailable — it does not remove it from
        # hass.states (that only happens on config entry *removal*).
        state = hass.states.get("camera.bosch_front_door")
        assert state is not None
        assert state.state == "unavailable"


async def test_setup_entry_without_any_token_fails(hass: HomeAssistant) -> None:
    """A config entry with no bearer/refresh token needs re-authentication.

    ConfigEntryAuthFailed (not UpdateFailed) so HA starts the native reauth
    flow instead of retrying a non-transient condition forever
    (bug-hunt 2026-07-27, Copilot review round 3).
    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_remove_entry_deletes_all_persisted_files(hass: HomeAssistant) -> None:
    """Full config-entry removal deletes every integration-owned Store file.

    Without this, the four Store files (cloud-outage flag, LAN IPs,
    hardware versions, LOCAL Digest credentials) and the persisted-snapshot
    directory all retained LAN credentials and camera images indefinitely
    after removal (bug-hunt 2026-07-27, Copilot review round 5).
    """
    _DOMAIN = DOMAIN

    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    for key in (
        f"{_DOMAIN}_cloud_alert_state",
        f"{_DOMAIN}_lan_ips",
        f"{_DOMAIN}_hw_versions",
        f"{_DOMAIN}_local_creds",
    ):
        await Store(hass, version=1, key=key).async_save({"x": 1})

    with patch(
        "homeassistant.components.bosch_shc_camera.async_remove_all_snapshots"
    ) as remove_snapshots:
        await async_remove_entry(hass, entry)
    remove_snapshots.assert_called_once_with(hass)

    for key in (
        f"{_DOMAIN}_cloud_alert_state",
        f"{_DOMAIN}_lan_ips",
        f"{_DOMAIN}_hw_versions",
        f"{_DOMAIN}_local_creds",
    ):
        assert await Store(hass, version=1, key=key).async_load() is None


async def test_persisted_local_creds_reject_unsafe_host(hass: HomeAssistant) -> None:
    """A poisoned/stale persisted LOCAL Digest cred entry must not be loaded.

    The fresh-creds path (coordinator.py's fetch_live_snapshot_local) only
    ever caches a host validated by `_is_safe_local_camera_host`. The
    persisted-store restore path in `__init__.py` read arbitrary
    `host`/`port` values straight out of HA's `.storage` JSON with no such
    check — a stale or previously-poisoned entry would bypass validation
    and let the outage-fallback snap fetch (camera.py's
    `_async_local_outage_snap`) send authenticated Digest credentials to
    an arbitrary host (Copilot review round 13).
    """
    _DOMAIN = DOMAIN
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    await Store(hass, version=1, key=f"{_DOMAIN}_local_creds").async_save(
        {
            CAM_ID: {
                "user": "admin",
                "password": "secret",
                "host": "8.8.8.8",  # public IP — not a physical camera's LAN address
                "port": 443,
            }
        }
    )

    coordinator_path = (
        "homeassistant.components.bosch_shc_camera.coordinator.BoschCameraCoordinator"
    )
    with (
        patch(
            f"{coordinator_path}._async_update_data",
            return_value=FAKE_COORDINATOR_DATA,
        ),
        patch(f"{coordinator_path}.async_fetch_live_snapshot", return_value=None),
        patch(f"{coordinator_path}.async_fetch_live_snapshot_local", return_value=None),
        patch(
            f"{coordinator_path}.async_fetch_fresh_event_snapshot", return_value=None
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert CAM_ID not in entry.runtime_data.local_creds_cache


async def test_persisted_local_creds_accept_safe_host(hass: HomeAssistant) -> None:
    """A genuine, private-LAN persisted cred entry is still loaded normally."""
    _DOMAIN = DOMAIN
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    await Store(hass, version=1, key=f"{_DOMAIN}_local_creds").async_save(
        {
            CAM_ID: {
                "user": "admin",
                "password": "secret",
                "host": "192.168.1.50",
                "port": 443,
            }
        }
    )

    coordinator_path = (
        "homeassistant.components.bosch_shc_camera.coordinator.BoschCameraCoordinator"
    )
    with (
        patch(
            f"{coordinator_path}._async_update_data",
            return_value=FAKE_COORDINATOR_DATA,
        ),
        patch(f"{coordinator_path}.async_fetch_live_snapshot", return_value=None),
        patch(f"{coordinator_path}.async_fetch_live_snapshot_local", return_value=None),
        patch(
            f"{coordinator_path}.async_fetch_fresh_event_snapshot", return_value=None
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.runtime_data.local_creds_cache[CAM_ID]["host"] == "192.168.1.50"


async def test_persisted_local_creds_skip_malformed_port(hass: HomeAssistant) -> None:
    """A corrupted/legacy port value must discard only that one record.

    `int(_payload.get("port", 443))` previously raised uncaught for a
    malformed value (e.g. a legacy `null` or `"not-a-port"`), which failed
    the entire config-entry setup — no cameras loaded — instead of just
    discarding the one bad credential record (Copilot review round 14).
    """
    _DOMAIN = DOMAIN
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    await Store(hass, version=1, key=f"{_DOMAIN}_local_creds").async_save(
        {
            CAM_ID: {
                "user": "admin",
                "password": "secret",
                "host": "192.168.1.50",
                "port": "not-a-port",
            }
        }
    )

    coordinator_path = (
        "homeassistant.components.bosch_shc_camera.coordinator.BoschCameraCoordinator"
    )
    with (
        patch(
            f"{coordinator_path}._async_update_data",
            return_value=FAKE_COORDINATOR_DATA,
        ),
        patch(f"{coordinator_path}.async_fetch_live_snapshot", return_value=None),
        patch(f"{coordinator_path}.async_fetch_live_snapshot_local", return_value=None),
        patch(
            f"{coordinator_path}.async_fetch_fresh_event_snapshot", return_value=None
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

    assert CAM_ID not in entry.runtime_data.local_creds_cache


async def test_cloud_degraded_startup_uses_spawn_tracked_not_bare_create_task(
    hass: HomeAssistant,
) -> None:
    """The cloud-degraded startup's LAN outage-ping is a tracked task.

    `_async_first_refresh_with_fallback` kicks an immediate
    `async_outage_ping_all()` so LAN-reachable sensors/fallbacks have a
    useful state right away. It must go through `coordinator.spawn_tracked`
    (landing in `bg_tasks`), not a bare `hass.async_create_task` — otherwise
    a removal/reload immediately after this degraded setup leaves it
    running against an already-torn-down coordinator instead of being
    cancelled by `_async_cancel_coordinator_tasks` (Copilot review
    round 10).
    """
    coordinator_path = (
        "homeassistant.components.bosch_shc_camera.coordinator.BoschCameraCoordinator"
    )
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            f"{coordinator_path}._async_update_data",
            return_value=FAKE_COORDINATOR_DATA,
        ),
        patch(f"{coordinator_path}.async_fetch_live_snapshot", return_value=None),
        patch(f"{coordinator_path}.async_fetch_live_snapshot_local", return_value=None),
        patch(
            f"{coordinator_path}.async_fetch_fresh_event_snapshot", return_value=None
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    def _spawn_tracked_capture(coro, *, name):
        coro.close()  # never actually scheduled here, avoid a leaked-coroutine warning

    with (
        patch(
            f"{coordinator_path}.async_config_entry_first_refresh",
            side_effect=ConfigEntryNotReady("cloud down"),
        ),
        patch(f"{coordinator_path}.async_outage_ping_all", return_value=None),
        patch(
            f"{coordinator_path}.spawn_tracked", side_effect=_spawn_tracked_capture
        ) as mock_spawn_tracked,
        patch(f"{coordinator_path}.async_fetch_live_snapshot", return_value=None),
        patch(f"{coordinator_path}.async_fetch_live_snapshot_local", return_value=None),
        patch(
            f"{coordinator_path}.async_fetch_fresh_event_snapshot", return_value=None
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_spawn_tracked.assert_called_once()
    assert (
        mock_spawn_tracked.call_args.kwargs["name"] == "bosch_shc_camera_startup_ping"
    )
    assert entry.runtime_data.last_update_success is False
