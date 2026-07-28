"""Coverage-gap tests for tick_housekeeping.py's post-tick housekeeping pass."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.components.bosch_shc_camera.coordinator import BoschCameraCoordinator
from homeassistant.components.bosch_shc_camera.tick_housekeeping import run_housekeeping
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CAM_ID = "AABBCCDD-1122-3344-5566-778899001122"


def _make_coordinator(hass: HomeAssistant) -> BoschCameraCoordinator:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={"bearer_token": "tok", "refresh_token": "rtok"},
        options={},
    )
    entry.add_to_hass(hass)
    return BoschCameraCoordinator(hass, entry)


async def test_housekeeping_announces_status_transition_for_each_camera(
    hass: HomeAssistant,
) -> None:
    """Non-first-tick with data must compute + spawn an announce per camera.

    Uses the real coordinator's own `_compute_status_for`/
    `_async_maybe_announce_camera_status` — the first observation for a
    camera is silent (records baseline), so this only asserts the pass
    completes without error and does spawn a tracked task per camera.
    """
    coordinator = _make_coordinator(hass)
    data = {CAM_ID: {"status": "ONLINE", "info": {"title": "Terrasse"}}}

    await run_housekeeping(coordinator, data, {}, now=0.0, is_first_tick=False)
    await hass.async_block_till_done()

    assert CAM_ID in coordinator._last_camera_status


async def test_housekeeping_persists_empty_hw_version_snapshot_on_last_camera_removed(
    hass: HomeAssistant,
) -> None:
    """Clearing the last camera's hw_version cache must still persist the empty snapshot.

    Same class of bug already fixed for LAN IPs and LOCAL creds (bug-hunt
    2026-07-27, Copilot review round 6) — a truthiness guard on the
    snapshot would skip the write and leave a removed camera's hardware
    version in `.storage` forever.
    """
    coordinator = _make_coordinator(hass)
    store = MagicMock()
    store.async_save = AsyncMock(return_value=None)
    coordinator.hw_version_store = store
    coordinator.hw_version = {}
    coordinator.hw_version_snapshot = {"OLD-CAM": "OUTDOOR"}

    await run_housekeeping(coordinator, {}, {}, now=0.0, is_first_tick=True)
    await hass.async_block_till_done()

    assert coordinator.hw_version_snapshot == {}
    store.async_save.assert_called_once_with({})


async def test_housekeeping_skips_hw_version_persist_when_snapshot_unchanged(
    hass: HomeAssistant,
) -> None:
    """An unchanged hw_version snapshot must not trigger a redundant save."""
    coordinator = _make_coordinator(hass)
    store = MagicMock()
    store.async_save = AsyncMock(return_value=None)
    coordinator.hw_version_store = store
    coordinator.hw_version = {CAM_ID: "OUTDOOR"}
    coordinator.hw_version_snapshot = {CAM_ID: "OUTDOOR"}

    await run_housekeeping(coordinator, {}, {}, now=0.0, is_first_tick=True)
    await hass.async_block_till_done()

    store.async_save.assert_not_called()


async def test_housekeeping_awaits_cloud_state_announce_directly(
    hass: HomeAssistant,
) -> None:
    """The final cloud-state announce is awaited directly (success=True) every tick.

    Calling it with an otherwise-idle coordinator (no prior outage) must
    hit the early-return no-op branch without raising.
    """
    coordinator = _make_coordinator(hass)

    await run_housekeeping(coordinator, {}, {}, now=0.0, is_first_tick=True)

    assert coordinator.cloud_outage_notified is False
