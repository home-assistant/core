"""Tests for stale-device removal + the user-driven remove callback.

Exercises:

* A ``@callback`` ``_remove_stale_devices()`` closure inside
  ``async_setup_entry`` that reconciles
  ``dr.async_entries_for_config_entry(...)`` against
  ``expected ∩ present`` (where ``expected = entry.data[CONF_VEHICLE_IDS]`` and
  ``present = {v.vehicle_id for v in garage_coordinator.data}``).  Devices
  outside the intersection are stale; the listener calls
  ``dr.async_remove_device(device.id)`` immediately for user-deselected
  vehicles and after ``_ABSENCE_THRESHOLD`` (= 2) consecutive misses for
  ABRP-side absent ones.  A ``misses: dict[int, int]`` closure accumulator
  tracks the consecutive count and is cleared whenever the vehicle
  re-appears.  Removal also calls ``telemetry_coordinator.forget_vehicle``
  to sweep the per-vehicle telemetry surfaces.
* The listener runs once eagerly at setup-time (before platform-forward) and
  is registered against ``garage_coordinator.async_add_listener`` for
  steady-state polls.
* A module-level ``async_remove_config_entry_device(hass, entry, device)``
  returning ``True`` unconditionally so the HA UI's "Delete from this
  integration" link works.

Behavioural assertions only — no direct ``misses`` peek. The counter-reset
oracle drives sequential polls and observes the device-survives /
device-removed transitions across them.

The garage is varied by reassigning ``mock_abrp_client.return_value`` to a
new ``list[AbrpVehicle]`` and driving ``garage_coordinator.async_refresh()``;
push telemetry is driven through ``fake_stream.fire_frame`` (the conftest
synchronous ``TelemetryStream`` double, which also collapses the setup
pre-warm sleep to 0).
"""

from typing import Any
from unittest.mock import AsyncMock

from aioabrp import AbrpApiError, AbrpVehicle, Metric, Telemetry
import pytest

import homeassistant.components.abetterrouteplanner as integration_module
from homeassistant.components.abetterrouteplanner import AbrpData
from homeassistant.components.abetterrouteplanner.const import CONF_VEHICLE_IDS, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    MOCK_VEHICLE_MODEL,
    MOCK_VEHICLE_MODEL_2,
    MOCK_VEHICLE_NAME,
    MOCK_VEHICLE_NAME_2,
    SENSOR_TEST_SUB,
    build_metric_value,
)

from tests.common import MockConfigEntry


def _make_vehicle(
    vehicle_id: int,
    name: str,
    vehicle_model: str,
) -> AbrpVehicle:
    """Build a minimal ``AbrpVehicle`` for stale-device tests."""
    return AbrpVehicle(
        vehicle_id=vehicle_id, name=name, vehicle_model=vehicle_model, paint=None
    )


def _device_scope(entry: MockConfigEntry, vehicle_id: int) -> str:
    """Return the device-identifier scope string for a given vehicle."""
    return f"{entry.unique_id}_{vehicle_id}"


_VEHICLE_A = _make_vehicle(MOCK_VEHICLE_ID, MOCK_VEHICLE_NAME, MOCK_VEHICLE_MODEL)
_VEHICLE_B = _make_vehicle(MOCK_VEHICLE_ID_2, MOCK_VEHICLE_NAME_2, MOCK_VEHICLE_MODEL_2)


async def _setup_integration(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockConfigEntry:
    """Register the integration's OAuth implementation and set up the entry."""
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _poll(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Trigger one garage-coordinator refresh and drain the event bus.

    Directly calls ``async_refresh()`` on the coordinator so tests do not
    need ``freezer`` (which would deadlock if the pre-warm sleep were not
    collapsed by ``fake_stream``).
    """
    runtime_data: AbrpData = entry.runtime_data
    await runtime_data.garage_coordinator.async_refresh()
    await hass.async_block_till_done()


def _two_vehicle_entry(token_entry: dict[str, Any]) -> MockConfigEntry:
    """Build a config entry tracking both vehicles A and B."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        },
    )


# ---------------------------------------------------------------------------
# user-deselect → device removed at setup-time (eager pass)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_user_deselect_removes_device_at_setup(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A device for a deselected vehicle is removed at the next entry reload.

    Scenario:
    1. Initial setup with ``CONF_VEHICLE_IDS=[A, B]`` and the mock returning both
       vehicles → both devices are registered by the sensor platform.
    2. User reconfigures to drop B → entry data updates to ``CONF_VEHICLE_IDS=[A]``.
    3. Entry reloads.  The eager setup-time pass of ``_remove_stale_devices``
       runs BEFORE platform-forward registers any entities against the
       now-deselected device, so device B is removed immediately — no
       waiting for the threshold counter (user intent is unambiguous).

    """
    entry = _two_vehicle_entry(token_entry)
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]
    await _setup_integration(hass, entry)

    scope_a = _device_scope(entry, MOCK_VEHICLE_ID)
    scope_b = _device_scope(entry, MOCK_VEHICLE_ID_2)
    assert device_registry.async_get_device(identifiers={(DOMAIN, scope_a)}) is not None
    assert device_registry.async_get_device(identifiers={(DOMAIN, scope_b)}) is not None

    # User reconfigure: keep only A.  Update the entry data and reload — the
    # config-flow reconfigure step would do the same via
    # ``async_update_reload_and_abort`` in production.
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_VEHICLE_IDS: [str(MOCK_VEHICLE_ID)]}
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert device_registry.async_get_device(identifiers={(DOMAIN, scope_a)}) is not None
    assert device_registry.async_get_device(identifiers={(DOMAIN, scope_b)}) is None


# ---------------------------------------------------------------------------
# ABRP-side deletion → removed after _ABSENCE_THRESHOLD misses
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
@pytest.mark.parametrize(
    ("absent_poll_count", "expected_present"),
    [
        pytest.param(1, True, id="one_miss_keeps_device"),
        pytest.param(2, False, id="two_misses_removes_device"),
    ],
)
async def test_abrp_side_deletion_removes_after_threshold(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    absent_poll_count: int,
    expected_present: bool,
) -> None:
    """Vehicle absent from N consecutive polls → device removed at N=threshold.

    Parametrized over the absence-poll count to lock the threshold (=2):
    after one miss the device must still exist (transient-blip tolerance);
    after two misses the device must be removed (the vehicle was deleted
    on the ABRP side, not just absent during a single 5xx blip).

    ``one_miss_keeps_device`` guards against any implementation that
    over-removes on a single miss; ``two_misses_removes_device`` is the
    positive case at the threshold.
    """
    entry = _two_vehicle_entry(token_entry)
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]
    await _setup_integration(hass, entry)

    scope_b = _device_scope(entry, MOCK_VEHICLE_ID_2)
    assert device_registry.async_get_device(identifiers={(DOMAIN, scope_b)}) is not None

    # B vanishes from upstream.  Drive ``absent_poll_count`` consecutive
    # refreshes; each one fires the listener.
    mock_abrp_client.return_value = [_VEHICLE_A]
    for _ in range(absent_poll_count):
        await _poll(hass, entry)

    device_b = device_registry.async_get_device(identifiers={(DOMAIN, scope_b)})
    assert (device_b is not None) is expected_present


# ---------------------------------------------------------------------------
# removal sweeps the per-vehicle telemetry surfaces via forget_vehicle
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_threshold_removal_forgets_telemetry_surfaces(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    fake_stream: Any,
) -> None:
    """Threshold removal calls ``forget_vehicle`` and clears its 4 surfaces.

    ``_remove_stale_devices`` is wired to
    ``telemetry_coordinator.forget_vehicle(vid)`` on every removal path so the
    in-memory telemetry maps stay honest with the device registry. This test
    drives a real telemetry frame into the coordinator for vehicle B first (so
    all four surfaces — ``data``, ``last_reported_at``, ``last_provider`` and
    the ``(vid, *)`` ``_presence_seen`` entries — are populated), then deletes B
    upstream and lets the listener fire to the threshold. After removal every
    surface for B must be cleared, while A's surfaces are untouched.

    Asserting the surface clearance (rather than mocking ``forget_vehicle``) is
    the behavioural proof that the removal path actually swept the telemetry
    state and not merely the device registry row.
    """
    entry = _two_vehicle_entry(token_entry)
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]
    await _setup_integration(hass, entry)

    runtime_data: AbrpData = entry.runtime_data
    telemetry = runtime_data.telemetry_coordinator

    # Populate all four per-vehicle surfaces for A and B via push frames. A
    # provider string is supplied so ``last_provider`` is non-empty, and the
    # metric is registered as a presence predicate so the frame records a
    # ``(vid, Metric)`` entry in ``_presence_seen``.
    telemetry.register_presence_predicates([Metric.SOC])
    fake_stream.fire_frame(
        MOCK_VEHICLE_ID,
        Telemetry(soc=build_metric_value(55.0, provider="tesla")),
    )
    fake_stream.fire_frame(
        MOCK_VEHICLE_ID_2,
        Telemetry(soc=build_metric_value(42.0, provider="tesla")),
    )

    # Pre-condition: B is present across all four surfaces.
    assert MOCK_VEHICLE_ID_2 in telemetry.data
    assert MOCK_VEHICLE_ID_2 in telemetry.last_reported_at
    assert MOCK_VEHICLE_ID_2 in telemetry.last_provider
    assert (MOCK_VEHICLE_ID_2, Metric.SOC) in telemetry._presence_seen

    scope_b = _device_scope(entry, MOCK_VEHICLE_ID_2)
    assert device_registry.async_get_device(identifiers={(DOMAIN, scope_b)}) is not None

    # B vanishes upstream; drive to the threshold so the device is removed.
    mock_abrp_client.return_value = [_VEHICLE_A]
    await _poll(hass, entry)
    await _poll(hass, entry)

    assert device_registry.async_get_device(identifiers={(DOMAIN, scope_b)}) is None

    # All four B surfaces swept; A's surfaces untouched.
    assert MOCK_VEHICLE_ID_2 not in telemetry.data
    assert MOCK_VEHICLE_ID_2 not in telemetry.last_reported_at
    assert MOCK_VEHICLE_ID_2 not in telemetry.last_provider
    assert not any(pair[0] == MOCK_VEHICLE_ID_2 for pair in telemetry._presence_seen)

    assert MOCK_VEHICLE_ID in telemetry.data
    assert MOCK_VEHICLE_ID in telemetry.last_reported_at
    assert MOCK_VEHICLE_ID in telemetry.last_provider
    assert (MOCK_VEHICLE_ID, Metric.SOC) in telemetry._presence_seen


# ---------------------------------------------------------------------------
# transient absence → device stays, counter resets
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_transient_absence_does_not_remove(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A one-poll blip then recovery must NOT trigger removal.

    Behavioural oracle for the counter-reset semantic (the
    ``misses`` accumulator is a closure variable, not externally
    observable):

    1. Poll 1 sets up A + B → both devices exist.
    2. Poll 2 returns A only → ``misses[B] = 1``.
    3. Poll 3 returns A + B → ``misses[B]`` resets to 0.
    4. Poll 4 returns A only → ``misses[B]`` becomes 1 again (NOT 2).

    Assert: device B is present after every poll, including poll 4.  If the
    counter were silently cumulative, poll 4 would push the count to 2 and
    remove the device — observing presence after poll 4 is the behavioural
    proof that the counter actually reset between polls 2 and 3.
    """
    entry = _two_vehicle_entry(token_entry)
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]
    await _setup_integration(hass, entry)
    scope_b = _device_scope(entry, MOCK_VEHICLE_ID_2)

    mock_abrp_client.return_value = [_VEHICLE_A]  # miss 1
    await _poll(hass, entry)
    assert device_registry.async_get_device(identifiers={(DOMAIN, scope_b)}) is not None

    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]  # reset
    await _poll(hass, entry)
    assert device_registry.async_get_device(identifiers={(DOMAIN, scope_b)}) is not None

    mock_abrp_client.return_value = [_VEHICLE_A]  # would be miss 2 if no reset
    await _poll(hass, entry)
    assert device_registry.async_get_device(identifiers={(DOMAIN, scope_b)}) is not None


# ---------------------------------------------------------------------------
# a failed poll cannot supply (or reset) the absence streak
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_failed_poll_does_not_advance_absence_counter(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A non-200 garage poll neither removes nor resets the absence streak.

    Only a successful (200) garage poll carries trustworthy presence: a failed
    fetch leaves ``coordinator.data`` at its last-good value, so the absence
    counter must ignore it entirely. Removal therefore requires two
    *successful* polls that both omit the vehicle — a transient failure between
    the first absent poll and the second can neither supply the second tick nor
    reset the streak.

    Sequence:
    * Setup: A + B → both devices registered.
    * Poll 1 (success): A only → ``misses[B] = 1``; B still present.
    * Poll 2 (failure): ``async_get_vehicles`` raises ``AbrpApiError`` →
      counter untouched; B still present.  This is the regression guard: the
      previous behaviour fired the listener against the stale "absent"
      ``data`` snapshot, ticked the count to 2, and removed B here.
    * Poll 3 (success): A only → ``misses[B] = 2`` → B removed, proving the
      streak survived the failure unchanged rather than resetting to 0.
    """
    entry = _two_vehicle_entry(token_entry)
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]
    await _setup_integration(hass, entry)
    scope_b = _device_scope(entry, MOCK_VEHICLE_ID_2)

    # Poll 1 (success): first trustworthy absent observation.
    mock_abrp_client.return_value = [_VEHICLE_A]
    await _poll(hass, entry)
    assert device_registry.async_get_device(identifiers={(DOMAIN, scope_b)}) is not None

    # Poll 2 (failure): the garage fetch errors; ``data`` stays at the
    # last-good (already-absent) snapshot.  Must NOT advance the counter.
    mock_abrp_client.side_effect = AbrpApiError("garage 503")
    await _poll(hass, entry)
    assert device_registry.async_get_device(identifiers={(DOMAIN, scope_b)}) is not None

    # Poll 3 (success): second trustworthy absent observation → removed.
    mock_abrp_client.side_effect = None
    mock_abrp_client.return_value = [_VEHICLE_A]
    await _poll(hass, entry)
    assert device_registry.async_get_device(identifiers={(DOMAIN, scope_b)}) is None


# ---------------------------------------------------------------------------
# manually renamed device is still removed when stale
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_manually_renamed_device_still_removed(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A user-renamed device is still removed once it's stale.

    ``device.name_by_user`` blocks the rename listener (preserves user
    overrides), but it does NOT block removal — the two semantics are
    orthogonal.  Removal means "this vehicle no longer exists in the
    selected ∩ present intersection"; the user's chosen label can't
    resurrect a deleted vehicle.

    Scenario:
    1. Set up A + B; user sets ``name_by_user="My Daily Driver"`` on B.
    2. ABRP deletes B (vanishes from coordinator data).
    3. Listener fires twice (threshold = 2) → device B removed.

    Guards against a patch that mistakenly extends the rename-listener's
    ``name_by_user`` guard to the removal path.
    """
    entry = _two_vehicle_entry(token_entry)
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]
    await _setup_integration(hass, entry)

    scope_b = _device_scope(entry, MOCK_VEHICLE_ID_2)
    device_b = device_registry.async_get_device(identifiers={(DOMAIN, scope_b)})
    assert device_b is not None
    device_registry.async_update_device(device_b.id, name_by_user="My Daily Driver")
    renamed = device_registry.async_get_device(identifiers={(DOMAIN, scope_b)})
    assert renamed is not None
    assert renamed.name_by_user == "My Daily Driver"

    mock_abrp_client.return_value = [_VEHICLE_A]
    await _poll(hass, entry)
    await _poll(hass, entry)

    assert device_registry.async_get_device(identifiers={(DOMAIN, scope_b)}) is None


# ---------------------------------------------------------------------------
# async_remove_config_entry_device returns True unconditionally
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_remove_config_entry_device_returns_true(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The module-level remove-device callback returns True for any device.

    HA's UI calls this callback when the user clicks "Delete from this
    integration".  It returns ``True`` unconditionally — for active devices
    (still in ``expected ∩ present``) AND for any other device — so the user
    always has an escape hatch regardless of current state.

    The function is looked up via ``getattr`` rather than imported at the
    top of the file so the missing-function failure surfaces inside the
    test instead of breaking the import for every other test in the file.
    """
    callback = getattr(integration_module, "async_remove_config_entry_device", None)
    assert callback is not None, (
        "async_remove_config_entry_device must be defined at module level"
    )

    entry = _two_vehicle_entry(token_entry)
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]
    await _setup_integration(hass, entry)

    scope_a = _device_scope(entry, MOCK_VEHICLE_ID)
    active_device = device_registry.async_get_device(identifiers={(DOMAIN, scope_a)})
    assert active_device is not None

    stale_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, _device_scope(entry, 999_000_001))},
        name="Stale Device",
    )

    assert await callback(hass, entry, active_device) is True
    assert await callback(hass, entry, stale_device) is True


# ---------------------------------------------------------------------------
# counter reset proven over four polls
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_counter_resets_on_reappearance(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Counter actually resets — not silently accumulated across re-appearances.

    Companion to ``test_transient_absence_does_not_remove``, which only
    walks polls 1-4 and asserts the device survives the post-reset miss.
    This test walks one more step (poll 5: another miss) and asserts the
    device is THEN removed — confirming the post-reset count reaches 2,
    not 3.  If the counter were cumulative, the device would have been
    removed at poll 4 (cumulative count 3 ≥ 2) and the poll-5 assertion
    would be redundant.

    Sequence:
    * Setup: A + B → both devices registered.
    * Poll 1: A only → ``misses[B] = 1``.
    * Poll 2: A + B → ``misses[B]`` reset to 0.
    * Poll 3: A only → ``misses[B] = 1``.
    * Poll 4: A only → ``misses[B] = 2`` → device B removed.

    Behavioural oracle (no direct ``misses`` peek):
    * After poll 3: device B still present (one miss after reset is
      below threshold).
    * After poll 4: device B gone.
    """
    entry = _two_vehicle_entry(token_entry)
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]
    await _setup_integration(hass, entry)
    scope_b = _device_scope(entry, MOCK_VEHICLE_ID_2)

    # Poll 1: miss
    mock_abrp_client.return_value = [_VEHICLE_A]
    await _poll(hass, entry)

    # Poll 2: reset
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]
    await _poll(hass, entry)

    # Poll 3: miss again — would be cumulative-count 3 if counter never reset
    mock_abrp_client.return_value = [_VEHICLE_A]
    await _poll(hass, entry)
    assert device_registry.async_get_device(identifiers={(DOMAIN, scope_b)}) is not None

    # Poll 4: second miss after reset — threshold hit, device removed
    await _poll(hass, entry)
    assert device_registry.async_get_device(identifiers={(DOMAIN, scope_b)}) is None


# ---------------------------------------------------------------------------
# devices with non-matching identifiers are left alone
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_non_matching_identifier_device_left_alone(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A device with an unparsable scope identifier is never removed.

    ``_vehicle_id_from_device`` is the defensive parser: it returns
    ``None`` when the identifier suffix isn't ``int``-coercible or
    doesn't share the expected ``{entry.unique_id}_`` prefix.  The
    listener then ``continue``s past it — the device is left untouched
    regardless of the current poll's vehicle set.

    Scenario:
    * Setup with ``CONF_VEHICLE_IDS=[A]`` and the mock returning A only.
    * Inject a junk device with identifier ``(DOMAIN, "garbage_scope")``
      linked to the entry (mimics a future migration leftover or a
      registry corruption).
    * Listener fires.
    * Assert: the junk device still exists.

    Active defensive guard against future regressions where the listener
    or the ``_vehicle_id_from_device`` parser admits non-parsable scope
    identifiers.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [str(MOCK_VEHICLE_ID)],
        },
    )
    mock_abrp_client.return_value = [_VEHICLE_A]
    await _setup_integration(hass, entry)

    junk_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "garbage_scope")},
        name="Junk",
    )
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, "garbage_scope")})
        is not None
    )

    await _poll(hass, entry)
    await _poll(hass, entry)

    surviving = device_registry.async_get_device(
        identifiers={(DOMAIN, "garbage_scope")}
    )
    assert surviving is not None
    assert surviving.id == junk_device.id
