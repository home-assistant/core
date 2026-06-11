"""Tests for dynamic-devices auto-discovery.

Zero-touch auto-add design:

* A entry-data field ``CONF_KNOWN_VEHICLE_IDS`` (``list[str]``) records every
  vehicle the user has had the opportunity to decline. Updated by config-flow
  (initial-add + reconfigure submit), and by the auto-add listener (each
  newly-discovered vehicle).
* In-place migration in ``async_setup_entry`` AFTER
  ``async_config_entry_first_refresh()``: if ``CONF_KNOWN_VEHICLE_IDS`` is missing
  from ``entry.data`` it is populated from the live garage at that moment.
* A third sibling listener ``_auto_add_new_vehicles`` registered on the garage
  coordinator AFTER the rename + stale-devices listeners (multi-listener
  order: rename → stale → auto-add). Computes ``new = present - known``; if
  non-empty, expands ``CONF_VEHICLE_IDS + CONF_KNOWN_VEHICLE_IDS`` and calls
  ``hass.config_entries.async_schedule_reload``.
* NOT called eagerly at setup. First fire is on the next coordinator refresh,
  so the reload-loop is impossible during setup.

Design notes
~~~~~~~~~~~~
* ``CONF_KNOWN_VEHICLE_IDS`` is referenced via ``getattr`` so the test file can
  load cleanly even if the constant is later renamed in production.
* Reload-detection uses a ``patch.object`` spy on
  ``hass.config_entries.async_schedule_reload`` — the patched callable is a
  no-op, so the auto-add ``entry.data`` update is observable but the entry
  itself is not torn down mid-test. This isolates the entry-data mutation
  from the reload side effect for clean assertions.
* The three-listeners assertion in ``test_three_sibling_listeners_registered``
  filters by ``__qualname__`` because any ``CoordinatorEntity`` instance that
  subscribes to the garage coordinator would inflate the count. Filtering by
  qualified name pins the architectural property we actually care about:
  three named sibling closures inside ``async_setup_entry``, independent of
  the entity-platform topology.
* Like ``test_stale_devices.py`` and ``test_vehicle_rename.py``, we avoid
  ``freezer`` and drive listener fires via ``coordinator.async_refresh()``
  directly. The garage is varied across polls by reassigning
  ``mock_abrp_client.return_value`` (the patched
  ``aioabrp.AbrpClient.async_get_vehicles``) between refreshes.
* Every test completes setup with a non-empty ``CONF_VEHICLE_IDS``, so each
  uses the ``fake_stream`` fixture: it patches the integration's
  ``TelemetryStream`` with a synchronous no-op double and collapses the setup
  pre-warm sleep to 0. The fake-stream class persists across the reload patch
  context, so a reload that re-runs setup reconstructs against it cleanly.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aioabrp import AbrpVehicle
import pytest

from homeassistant.components.abetterrouteplanner import AbrpData, const as abrp_const
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
)

from tests.common import MockConfigEntry

# The entry-data key string is ``"known_vehicle_ids"``. Pulled via ``getattr``
# so this file imports cleanly even if the constant is later renamed in
# production — the constant and the fallback below must agree or the
# tests will silently drift.
CONF_KNOWN_VEHICLE_IDS: str = getattr(
    abrp_const, "CONF_KNOWN_VEHICLE_IDS", "known_vehicle_ids"
)

# A third vehicle id, distinct from the two seeded by conftest, for the
# "new vehicle appears mid-life" scenarios. Large + on-domain so a stray
# print stands out in test failures.
MOCK_VEHICLE_ID_3 = 888_777_666_555
MOCK_VEHICLE_NAME_3 = "Brand New Test Vehicle"
MOCK_VEHICLE_MODEL_3 = "rivian:r3:27:base:rwd:w23"

MOCK_VEHICLE_ID_4 = 777_666_555_444
MOCK_VEHICLE_NAME_4 = "Another Brand New Vehicle"
MOCK_VEHICLE_MODEL_4 = "tesla:m3:27:lr:awd:w24"


def _make_vehicle(
    vehicle_id: int,
    name: str,
    vehicle_model: str,
) -> AbrpVehicle:
    """Build a minimal ``AbrpVehicle`` with paint=None for dynamic-devices tests."""
    return AbrpVehicle(
        vehicle_id=vehicle_id, name=name, vehicle_model=vehicle_model, paint=None
    )


def _device_scope(entry: MockConfigEntry, vehicle_id: int) -> str:
    """Return the device-identifier scope string for a given vehicle."""
    return f"{entry.unique_id}_{vehicle_id}"


_VEHICLE_A = _make_vehicle(MOCK_VEHICLE_ID, MOCK_VEHICLE_NAME, MOCK_VEHICLE_MODEL)
_VEHICLE_B = _make_vehicle(MOCK_VEHICLE_ID_2, MOCK_VEHICLE_NAME_2, MOCK_VEHICLE_MODEL_2)
_VEHICLE_C = _make_vehicle(MOCK_VEHICLE_ID_3, MOCK_VEHICLE_NAME_3, MOCK_VEHICLE_MODEL_3)
_VEHICLE_D = _make_vehicle(MOCK_VEHICLE_ID_4, MOCK_VEHICLE_NAME_4, MOCK_VEHICLE_MODEL_4)


async def _setup_integration(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockConfigEntry:
    """Register the integration's OAuth implementation and set up the entry.

    The ``fake_stream`` fixture collapses the setup pre-warm sleep to 0, so
    setup returns without the real-time wait.
    """
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _poll(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Trigger one garage-coordinator refresh and drain the event bus."""
    runtime_data: AbrpData = entry.runtime_data
    await runtime_data.garage_coordinator.async_refresh()
    await hass.async_block_till_done()


def _build_entry(
    token_entry: dict[str, Any],
    *,
    vehicle_ids: list[str],
    known_vehicle_ids: list[str] | None,
) -> MockConfigEntry:
    """Build a ``MockConfigEntry`` with optional ``CONF_KNOWN_VEHICLE_IDS``.

    ``known_vehicle_ids=None`` simulates a legacy upgrade entry — the field is
    absent and the in-place migration block must populate it. Pass a list
    (including ``[]``) to simulate a current entry where the migration is a
    no-op.
    """
    data: dict[str, Any] = {
        "auth_implementation": DOMAIN,
        "token": token_entry,
        CONF_VEHICLE_IDS: vehicle_ids,
    }
    if known_vehicle_ids is not None:
        data[CONF_KNOWN_VEHICLE_IDS] = known_vehicle_ids
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data=data,
    )


@contextmanager
def _spy_schedule_reload(hass: HomeAssistant) -> Iterator[MagicMock]:
    """Patch ``async_schedule_reload`` with a no-op spy and yield the mock.

    The patched callable is a no-op (returns ``None``) so the entry remains
    LOADED across the test even if the listener "schedules a reload". This
    isolates the entry-data mutation side of the listener from the actual
    reload teardown, which is exercised separately by HA's own framework
    tests.

    Context-managed so the patch is reliably stopped at end-of-``with`` —
    a global ``patch.stopall()`` would also tear down pytest-socket's autouse
    network block, causing subsequent tests in the file to fail at
    ``async_setup_component(hass, "auth")``.
    """
    spy = MagicMock(return_value=None)
    with patch.object(hass.config_entries, "async_schedule_reload", spy):
        yield spy


# ---------------------------------------------------------------------------
# fresh install: KNOWN already populated, listener no-op first cycle
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_fresh_install_no_reload_on_first_listener_fire(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
) -> None:
    """A fresh install's first listener fire after setup must NOT schedule reload.

    Config-flow's ``async_step_pick_vehicles`` populates BOTH
    ``CONF_VEHICLE_IDS`` and ``CONF_KNOWN_VEHICLE_IDS`` with the full garage at
    submit time. The next coordinator refresh sees ``new = present - known =
    {}`` and is a no-op.

    Specifically asserts:
    * ``async_schedule_reload`` was NOT called during ``async_setup_entry``.
    * After one steady-state poll, ``async_schedule_reload`` still not called
      and ``CONF_VEHICLE_IDS`` / ``CONF_KNOWN_VEHICLE_IDS`` are untouched.
    """
    entry = _build_entry(
        token_entry,
        vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        known_vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
    )
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]

    with _spy_schedule_reload(hass) as schedule_spy:
        await _setup_integration(hass, entry)
        assert schedule_spy.call_count == 0

        await _poll(hass, entry)
        assert schedule_spy.call_count == 0

    assert sorted(entry.data[CONF_VEHICLE_IDS]) == sorted(
        [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)]
    )
    assert sorted(entry.data[CONF_KNOWN_VEHICLE_IDS]) == sorted(
        [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)]
    )


# ---------------------------------------------------------------------------
# migration seeds KNOWN to live garage
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
@pytest.mark.parametrize(
    ("vehicle_ids", "expected_known"),
    [
        pytest.param(
            [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
            sorted([str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)]),
            id="all_selected_known_equals_live",
        ),
        pytest.param(
            [str(MOCK_VEHICLE_ID)],
            sorted([str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)]),
            id="some_deselected_known_still_equals_live",
        ),
    ],
)
async def test_migration_seeds_known_to_live_garage(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    vehicle_ids: list[str],
    expected_known: list[str],
) -> None:
    """An upgraded entry without ``CONF_KNOWN_VEHICLE_IDS`` is seeded post-refresh.

    Migration runs AFTER ``async_config_entry_first_refresh()`` so the seed
    value is the LIVE garage at that moment — every pre-existing vehicle is
    considered "known" regardless of whether the user previously selected it.
    Pre-upgrade-deselected vehicles therefore stay permanently declined.

    Parametrized:
    * ``all_selected_known_equals_live`` — user had both A + B selected pre-
      upgrade; migration writes KNOWN=[A, B] equal to VEHICLE_IDS=[A, B]. No
      auto-add on next poll.
    * ``some_deselected_known_still_equals_live`` — user had only A selected;
      migration writes KNOWN=[A, B]. B is now "known but declined" and stays
      out of VEHICLE_IDS forever. No auto-add on next poll.
    """
    entry = _build_entry(token_entry, vehicle_ids=vehicle_ids, known_vehicle_ids=None)
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]

    with _spy_schedule_reload(hass) as schedule_spy:
        await _setup_integration(hass, entry)

    assert CONF_KNOWN_VEHICLE_IDS in entry.data, (
        "migration must populate CONF_KNOWN_VEHICLE_IDS after first refresh"
    )
    assert sorted(entry.data[CONF_KNOWN_VEHICLE_IDS]) == expected_known
    # VEHICLE_IDS is untouched by migration; it remains exactly what the user had.
    assert sorted(entry.data[CONF_VEHICLE_IDS]) == sorted(vehicle_ids)
    # Migration itself must NOT cause a reload (no recursive-loop risk).
    assert schedule_spy.call_count == 0


# ---------------------------------------------------------------------------
# migration is idempotent when KNOWN already present
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_migration_idempotent_when_known_already_present(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
) -> None:
    """An entry that already has ``CONF_KNOWN_VEHICLE_IDS`` must NOT be overwritten.

    The migration uses a strict ``if CONF_KNOWN_VEHICLE_IDS not in entry.data``
    membership check, so a previously-migrated entry whose live garage has
    since shrunk does not lose declined-vehicle history.

    Scenario: entry.data already has ``KNOWN=[A, B]`` from a prior setup; live
    garage now returns only ``[A]`` (B was deleted in ABRP later). Migration
    must leave ``KNOWN=[A, B]`` intact — B's declined state survives.

    Guards against a buggy ``entry.data.get(CONF_KNOWN_VEHICLE_IDS, []) == []``
    style check that would clobber the field.
    """
    entry = _build_entry(
        token_entry,
        vehicle_ids=[str(MOCK_VEHICLE_ID)],
        known_vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
    )
    mock_abrp_client.return_value = [_VEHICLE_A]  # B deleted upstream

    with _spy_schedule_reload(hass) as schedule_spy:
        await _setup_integration(hass, entry)

    assert sorted(entry.data[CONF_KNOWN_VEHICLE_IDS]) == sorted(
        [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)]
    )
    assert sorted(entry.data[CONF_VEHICLE_IDS]) == [str(MOCK_VEHICLE_ID)]
    assert schedule_spy.call_count == 0


# ---------------------------------------------------------------------------
# new vehicle post-setup: auto-add + reload
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_new_vehicle_auto_added_and_reload_scheduled(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
) -> None:
    """A vehicle appearing post-setup is auto-onboarded AND triggers reload.

    Scenario:
    1. Setup with ``VEHICLE_IDS=[A, B]`` and ``KNOWN=[A, B]``; garage returns A, B.
    2. ABRP adds vehicle C; next poll returns A, B, C.
    3. Listener fires: ``new = {C}``; ``VEHICLE_IDS`` and ``KNOWN`` both extended;
       ``async_schedule_reload`` called exactly once.

    Asserts the listener performs a SINGLE atomic ``entry.data`` update (both
    fields written together) followed by exactly one ``async_schedule_reload``
    call.
    """
    entry = _build_entry(
        token_entry,
        vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        known_vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
    )
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]

    with _spy_schedule_reload(hass) as schedule_spy:
        await _setup_integration(hass, entry)
        assert schedule_spy.call_count == 0

        mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B, _VEHICLE_C]
        await _poll(hass, entry)

    expected_set = {
        str(MOCK_VEHICLE_ID),
        str(MOCK_VEHICLE_ID_2),
        str(MOCK_VEHICLE_ID_3),
    }
    assert set(entry.data[CONF_VEHICLE_IDS]) == expected_set
    assert set(entry.data[CONF_KNOWN_VEHICLE_IDS]) == expected_set
    schedule_spy.assert_called_once_with(entry.entry_id)


# ---------------------------------------------------------------------------
# multiple new vehicles in one poll → single reload
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_multiple_new_vehicles_added_in_single_reload(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
) -> None:
    """Two new vehicles in a single poll → ONE entry update + ONE reload.

    Scenario:
    1. Setup with ``VEHICLE_IDS=[A, B]`` and ``KNOWN=[A, B]``; garage returns A, B.
    2. ABRP adds C AND D; next poll returns A, B, C, D.
    3. Listener fires: ``new = {C, D}`` (computed as a set, not per-vehicle);
       both added to ``VEHICLE_IDS`` + ``KNOWN`` in a single ``async_update_entry``
       call; ``async_schedule_reload`` called exactly once.

    Locks the listener shape against an implementation that would iterate
    per-vehicle and trigger N reloads for N new vehicles — that would race the
    reload teardown.
    """
    entry = _build_entry(
        token_entry,
        vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        known_vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
    )
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]

    with _spy_schedule_reload(hass) as schedule_spy:
        await _setup_integration(hass, entry)

        mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B, _VEHICLE_C, _VEHICLE_D]
        await _poll(hass, entry)

    expected_set = {
        str(MOCK_VEHICLE_ID),
        str(MOCK_VEHICLE_ID_2),
        str(MOCK_VEHICLE_ID_3),
        str(MOCK_VEHICLE_ID_4),
    }
    assert set(entry.data[CONF_VEHICLE_IDS]) == expected_set
    assert set(entry.data[CONF_KNOWN_VEHICLE_IDS]) == expected_set
    schedule_spy.assert_called_once_with(entry.entry_id)


# ---------------------------------------------------------------------------
# declined vehicle: in KNOWN but not VEHICLE_IDS → never re-added
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_user_declined_vehicle_does_not_re_add(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
) -> None:
    """A vehicle in KNOWN but absent from VEHICLE_IDS is never re-added.

    This is the spouse-vehicle / rental-vehicle escape hatch: the user has explicitly
    declined this vehicle once via reconfigure; the listener must respect that
    decision on every subsequent poll forever.

    Scenario:
    1. Setup with ``VEHICLE_IDS=[A]`` and ``KNOWN=[A, B, C]``; garage returns
       A, B, C.
    2. Listener fires repeatedly (we drive 3 polls); ``new = present - known
       = {} - {A,B,C} = {}``. No mutation, no reload, ever.

    Guards against an implementation that uses ``present - selected`` (would
    erroneously add B and C) instead of ``present - known``.
    """
    entry = _build_entry(
        token_entry,
        vehicle_ids=[str(MOCK_VEHICLE_ID)],
        known_vehicle_ids=[
            str(MOCK_VEHICLE_ID),
            str(MOCK_VEHICLE_ID_2),
            str(MOCK_VEHICLE_ID_3),
        ],
    )
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B, _VEHICLE_C]

    with _spy_schedule_reload(hass) as schedule_spy:
        await _setup_integration(hass, entry)

        for _ in range(3):
            await _poll(hass, entry)

    assert sorted(entry.data[CONF_VEHICLE_IDS]) == [str(MOCK_VEHICLE_ID)]
    assert sorted(entry.data[CONF_KNOWN_VEHICLE_IDS]) == sorted(
        [
            str(MOCK_VEHICLE_ID),
            str(MOCK_VEHICLE_ID_2),
            str(MOCK_VEHICLE_ID_3),
        ]
    )
    assert schedule_spy.call_count == 0


# ---------------------------------------------------------------------------
# disappear/reappear with device intact: no reload, no VEHICLE_IDS change
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_disappear_then_reappear_no_reload(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Transient disappear+reappear (single miss, device still registered) is a no-op.

    The vehicle's device row never went away — the threshold counter caught
    one miss and didn't remove. When the vehicle reappears in the next poll,
    the auto-add listener sees:
    * ``new = present - known = {}`` (B is in KNOWN).
    * device for B is already registered (single-miss didn't remove it).
    → no reload, no ``VEHICLE_IDS`` mutation. Entities transition unavailable →
    available naturally via the coordinator's existing state machine.

    Sequence:
    1. Setup with both A + B selected and known; garage returns A + B.
    2. Poll: garage returns A only (single miss; B's device survives by the stale-devices cleanup).
    3. Poll: garage returns A + B again.
    4. Assert: no reload was scheduled; ``VEHICLE_IDS`` and ``KNOWN`` unchanged.

    Guards against an implementation that triggers a spurious reload on every
    "device exists + vehicle re-present" event.
    """
    entry = _build_entry(
        token_entry,
        vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        known_vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
    )
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]

    with _spy_schedule_reload(hass) as schedule_spy:
        await _setup_integration(hass, entry)

        # Device B is registered post-setup
        scope_b = _device_scope(entry, MOCK_VEHICLE_ID_2)
        assert (
            device_registry.async_get_device(identifiers={(DOMAIN, scope_b)})
            is not None
        )

        mock_abrp_client.return_value = [_VEHICLE_A]
        await _poll(hass, entry)
        # Device B still present (single miss < threshold).
        assert (
            device_registry.async_get_device(identifiers={(DOMAIN, scope_b)})
            is not None
        )

        mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]
        await _poll(hass, entry)

    assert schedule_spy.call_count == 0
    assert sorted(entry.data[CONF_VEHICLE_IDS]) == sorted(
        [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)]
    )
    assert sorted(entry.data[CONF_KNOWN_VEHICLE_IDS]) == sorted(
        [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)]
    )


# ---------------------------------------------------------------------------
# re-appearance after stale removal: reload without VEHICLE_IDS mutation
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_re_appearance_after_stale_removal_schedules_reload(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A previously-removed by the stale-devices cleanup device re-registers on next presence.

    The listener's device-replacement path:
    ``expected_devices = (selected | new_vehicles) & present``
    ``missing_devices = expected_devices - existing_devices``
    If ``missing_devices`` is non-empty → schedule reload. ``VEHICLE_IDS`` is NOT
    mutated (B is already there) — only the reload re-registers the device.

    Scenario:
    1. Setup with A + B selected; both in KNOWN.
    2. Simulate stale-devices cleanup: manually remove device B from the registry (mimics two
       missed polls already having elapsed before this test began).
    3. Next poll: garage returns A + B (B is back).
    4. Listener fires: ``new = {}``, ``missing_devices = {B}`` → reload
       scheduled. ``VEHICLE_IDS`` unchanged.
    """
    entry = _build_entry(
        token_entry,
        vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        known_vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
    )
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]

    with _spy_schedule_reload(hass) as schedule_spy:
        await _setup_integration(hass, entry)

        scope_b = _device_scope(entry, MOCK_VEHICLE_ID_2)
        device_b = device_registry.async_get_device(identifiers={(DOMAIN, scope_b)})
        assert device_b is not None

        # Simulate having already removed B (e.g. two prior absent polls).
        device_registry.async_remove_device(device_b.id)
        assert device_registry.async_get_device(identifiers={(DOMAIN, scope_b)}) is None

        # B reappears on next garage poll.
        mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]
        await _poll(hass, entry)

    schedule_spy.assert_called_once_with(entry.entry_id)
    # VEHICLE_IDS untouched: B was already selected, the reload only re-registers.
    assert sorted(entry.data[CONF_VEHICLE_IDS]) == sorted(
        [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)]
    )
    assert sorted(entry.data[CONF_KNOWN_VEHICLE_IDS]) == sorted(
        [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)]
    )


# ---------------------------------------------------------------------------
# three sibling listeners all registered post-setup
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_three_sibling_listeners_registered(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
) -> None:
    """After setup, the three named sibling closures are all registered.

    The three listeners — rename + stale-devices + auto-add — are each an
    independent ``@callback`` registered via
    ``entry.async_on_unload(garage_coordinator.async_add_listener(...))``.

    The garage coordinator picks up one ``_handle_coordinator_update``
    listener per ``CoordinatorEntity`` subscriber as well, so a raw
    ``len(coordinator._listeners)`` count moves with the entity-platform
    topology and is the wrong thing to assert on. We filter to the three named
    integration closures by qualified name — that's the architectural
    property worth pinning: three named siblings, no accidental
    consolidation into a single multi-purpose closure.

    ``_auto_add_new_vehicles`` is built by ``_make_auto_add_listener`` (a
    module-level factory function extracted to keep ``async_setup_entry``
    under the C901 cyclomatic-complexity budget), so its parent qualname is
    ``_make_auto_add_listener`` rather than ``async_setup_entry`` — the two
    other closures still live directly inside ``async_setup_entry``.
    """
    entry = _build_entry(
        token_entry,
        vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        known_vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
    )
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]

    with _spy_schedule_reload(hass) as schedule_spy:
        await _setup_integration(hass, entry)

    runtime_data: AbrpData = entry.runtime_data
    closure_qualnames = {
        getattr(cb, "__qualname__", "")
        for cb, _ in runtime_data.garage_coordinator._listeners.values()
        if any(
            parent in getattr(cb, "__qualname__", "")
            for parent in (
                "async_setup_entry.<locals>",
                "_make_auto_add_listener.<locals>",
            )
        )
    }
    assert closure_qualnames == {
        "async_setup_entry.<locals>._propagate_renames",
        "async_setup_entry.<locals>._remove_stale_devices",
        "_make_auto_add_listener.<locals>._auto_add_new_vehicles",
    }
    # Setup itself must not have scheduled a reload.
    assert schedule_spy.call_count == 0


# ---------------------------------------------------------------------------
# reload idempotency across two consecutive identical polls
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
@pytest.mark.parametrize(
    ("poll1_vehicles", "poll2_vehicles", "expected_final_set"),
    [
        pytest.param(
            [_VEHICLE_A, _VEHICLE_C],
            [_VEHICLE_A, _VEHICLE_C],
            {str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_3)},
            id="same_vehicle_short_circuits_on_empty_triggering",
        ),
        pytest.param(
            [_VEHICLE_A, _VEHICLE_C],
            [_VEHICLE_A, _VEHICLE_C, _VEHICLE_D],
            {
                str(MOCK_VEHICLE_ID),
                str(MOCK_VEHICLE_ID_3),
                str(MOCK_VEHICLE_ID_4),
            },
            id="different_vehicle_short_circuits_on_already_pending",
        ),
    ],
)
async def test_reload_coalesces_back_to_back_polls(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    poll1_vehicles: list[AbrpVehicle],
    poll2_vehicles: list[AbrpVehicle],
    expected_final_set: set[str],
) -> None:
    """Back-to-back polls before reload teardown → exactly one reload, both states merged.

    Two distinct short-circuit paths inside ``_auto_add_new_vehicles`` deliver
    the same observable contract (exactly one ``async_schedule_reload`` call
    across the two polls) but exercise different code:

    * ``same_vehicle_short_circuits_on_empty_triggering`` — poll 2 returns
      the SAME garage as poll 1 (both add ``C``). After poll 1 ``KNOWN``
      contains ``C`` and ``reload_pending = {C}``; poll 2's
      ``new = present - known = {}`` and ``triggering = ({} | {}) -
      reload_pending = {}`` → the ``if not triggering: return`` guard exits
      before any data write or schedule call.

    * ``different_vehicle_short_circuits_on_already_pending`` — poll 2's
      garage adds a SECOND new vehicle ``D`` on top of the still-pending
      ``C``. Poll 2 computes ``new = {D}`` (non-empty), so the ``triggering``
      guard does NOT short-circuit. The listener updates ``entry.data`` to
      include ``D``, then captures ``already_pending = True`` (``reload_pending``
      still holds ``C``) and SKIPS the second ``async_schedule_reload``
      call. Both vehicles are accumulated into ``reload_pending`` so the
      eventual reload sees the merged state.

    The same-vehicle case is the easier path to reason about; the different-
    vehicle case is what the ``already_pending`` guard actually exists for — a
    regression that moved the ``bool(reload_pending)`` capture AFTER the
    ``reload_pending.update(...)`` call would silently schedule two reloads and
    would only be caught by the second parametrize case.

    Both assertions:
    * ``schedule_spy.call_count == 1`` (coalesced).
    * ``entry.data[CONF_VEHICLE_IDS] == entry.data[CONF_KNOWN_VEHICLE_IDS] ==
      expected_final_set`` — state writes happen on every triggering poll,
      only the reload itself is deduped.
    """
    entry = _build_entry(
        token_entry,
        vehicle_ids=[str(MOCK_VEHICLE_ID)],
        known_vehicle_ids=[str(MOCK_VEHICLE_ID)],
    )
    mock_abrp_client.return_value = [_VEHICLE_A]

    with _spy_schedule_reload(hass) as schedule_spy:
        await _setup_integration(hass, entry)

        mock_abrp_client.return_value = poll1_vehicles
        await _poll(hass, entry)

        mock_abrp_client.return_value = poll2_vehicles
        await _poll(hass, entry)

    schedule_spy.assert_called_once_with(entry.entry_id)
    assert set(entry.data[CONF_VEHICLE_IDS]) == expected_final_set
    assert set(entry.data[CONF_KNOWN_VEHICLE_IDS]) == expected_final_set


# ---------------------------------------------------------------------------
# empty live garage with non-empty VEHICLE_IDS: no mass-decline
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_empty_live_garage_does_not_mass_decline(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
) -> None:
    """Empty live garage on a poll must NOT touch VEHICLE_IDS or KNOWN.

    Defensive guard against an auth glitch or API blip returning an empty
    ``result`` array. The listener computes ``new = present - known = {} -
    {A,B} = {}`` — there's literally nothing to add. ``VEHICLE_IDS`` and
    ``KNOWN`` are entirely independent of "what's in present" — they're a
    history of user decisions and would lose meaning if cleared on a single
    bad poll.

    Specifically guards against an alternate implementation that "syncs"
    ``VEHICLE_IDS`` to ``present`` (would mass-deselect everything on an empty
    response) or "syncs" ``KNOWN`` to ``present`` (would lose decline
    history).
    """
    entry = _build_entry(
        token_entry,
        vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        known_vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
    )
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]

    with _spy_schedule_reload(hass) as schedule_spy:
        await _setup_integration(hass, entry)

        mock_abrp_client.return_value = []
        await _poll(hass, entry)

    assert sorted(entry.data[CONF_VEHICLE_IDS]) == sorted(
        [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)]
    )
    assert sorted(entry.data[CONF_KNOWN_VEHICLE_IDS]) == sorted(
        [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)]
    )
    assert schedule_spy.call_count == 0
    # Entry remains LOADED — empty garage is not a fatal state.
    assert entry.state is ConfigEntryState.LOADED


# ---------------------------------------------------------------------------
# deferred migration seed on first non-empty poll
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_deferred_migration_seeds_on_first_non_empty_poll(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
) -> None:
    """Empty-garage first-refresh defers the ``KNOWN`` seed to the first non-empty poll.

    A legacy entry whose first garage refresh returns an empty array (auth
    glitch, rate-limit, ABRP-side outage) must NOT have
    ``CONF_KNOWN_VEHICLE_IDS`` seeded to ``[]`` at setup time — otherwise
    the next non-empty poll would treat every pre-upgrade-deselected vehicle
    as "new" and auto-onboard it (mass-onboarding bug).

    Instead, the setup-time migration block skips on empty data, and the
    listener's deferred-seed branch handles the first non-empty poll: seed
    ``KNOWN`` to the current live garage and return early — no auto-add
    evaluation on that cycle. The seed snapshot freezes the decline history
    at the first observable moment.

    Sequence:
    1. legacy entry — ``VEHICLE_IDS=[A]``, NO ``CONF_KNOWN_VEHICLE_IDS`` key.
       Historically the user had B in their ABRP garage but never selected
       it (so B should remain declined post-upgrade).
    2. Mock garage returns ``[]`` for ``async_config_entry_first_refresh``.
    3. Setup completes (empty garage is non-fatal — sensor platform forwards
       with zero vehicles).
       Assert: ``CONF_KNOWN_VEHICLE_IDS`` still NOT in ``entry.data``.
    4. Mock garage now returns ``[A, B]`` (the historical reality).
    5. Poll.
       Assert: listener's deferred-seed branch wrote ``KNOWN = sorted([A, B])``,
       ``VEHICLE_IDS`` untouched at ``[A]``, no ``async_schedule_reload`` call
       (deferred-seed path returns before reaching the auto-add path).

    Guards against an implementation that:
    * Seeds ``KNOWN=[]`` at setup despite empty garage → next poll treats
      every garage vehicle as new → mass-onboarding.
    * Runs the auto-add path inside the deferred-seed branch → B would be
      added to ``VEHICLE_IDS`` despite never having been selected pre-upgrade.
    """
    entry = _build_entry(
        token_entry,
        vehicle_ids=[str(MOCK_VEHICLE_ID)],
        known_vehicle_ids=None,
    )
    mock_abrp_client.return_value = []

    with _spy_schedule_reload(hass) as schedule_spy:
        await _setup_integration(hass, entry)
        # empty first-refresh must NOT seed KNOWN.
        assert CONF_KNOWN_VEHICLE_IDS not in entry.data
        assert schedule_spy.call_count == 0

        mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]
        await _poll(hass, entry)

    assert sorted(entry.data[CONF_KNOWN_VEHICLE_IDS]) == sorted(
        [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)]
    )
    # B was never in VEHICLE_IDS pre-upgrade; the deferred-seed branch must NOT
    # auto-onboard it. It is now "known but not selected" → declined forever.
    assert sorted(entry.data[CONF_VEHICLE_IDS]) == [str(MOCK_VEHICLE_ID)]
    assert schedule_spy.call_count == 0
    assert entry.state is ConfigEntryState.LOADED
