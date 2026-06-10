"""Tests for the diagnostics platform of A Better Routeplanner.

Three oracles, each guarding a different facet of the rule:

* ``test_diagnostics_snapshot`` — primary shape oracle.  Drives a loaded
  entry with two vehicles (one selected, one declined) plus one applied
  SSE frame, then Syrupy-snapshots the full diagnostics payload.  Snapshot
  lives at ``snapshots/test_diagnostics.ambr``; regenerate via
  ``--snapshot-update`` after deliberate shape changes only.

* ``test_diagnostics_no_secrets_leak`` — load-bearing redaction oracle.
  Stuffs distinctive sentinel strings into ``access_token``,
  ``refresh_token``, and ``id_token``; calls diagnostics; serialises the
  result to JSON; asserts NONE of the sentinels appear anywhere in the
  serialised output.  Regression guard against any future field that
  bypasses ``async_redact_data``.

* ``test_diagnostics_presence_state_reflects_seen_set`` — predicate /
  seen-set oracle.  Drives two SSE frames (vehicle A → ``soc`` value,
  vehicle B → ``power`` value); asserts ``presence_seen`` contains exactly
  those two pairs and ``presence_predicates`` is the sorted list of
  registered metric keys.

The 0.5 s real-time pre-warm sleep is accepted — patching ``asyncio.sleep``
module-globally short-circuits the SSE retry backoff and hangs setup.
``CONF_KNOWN_VEHICLE_IDS`` is accessed via ``getattr`` with a literal fallback
so the file imports cleanly even if a future refactor renames the const.

The presence-state surface is nested under
``result["telemetry_coordinator"]`` as ``presence_seen`` and
``presence_predicates_registered``.
"""

from datetime import UTC, datetime
import json
from typing import Any
from unittest.mock import AsyncMock

from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.abetterrouteplanner import AbrpData, const as abrp_const
from homeassistant.components.abetterrouteplanner.api import AbrpVehicle
from homeassistant.components.abetterrouteplanner.const import CONF_VEHICLE_IDS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    MOCK_VEHICLE_MODEL,
    MOCK_VEHICLE_MODEL_2,
    MOCK_VEHICLE_NAME,
    MOCK_VEHICLE_NAME_2,
    SENSOR_TEST_SUB,
    build_telemetry_frame,
)

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

CONF_KNOWN_VEHICLE_IDS: str = getattr(
    abrp_const, "CONF_KNOWN_VEHICLE_IDS", "known_vehicle_ids"
)

# Deterministic timestamps baked into the snapshot oracle so it stays
# stable across runs. ``freezer`` was tried first but interacts badly with
# the authenticated ``hass_client`` (freezing the wall clock breaks the
# pre-issued access token validation). Instead, we run setup under real
# time, then overwrite the two natively-stamped fields on the runtime
# coordinators before calling diagnostics — the resulting snapshot pins
# the *shape* of the dict, not the timestamp-generation behavior (which
# is exercised by the framework's own DataUpdateCoordinator tests).
_FROZEN_LAST_UPDATE_TIME = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)
_FROZEN_LAST_CONNECT_ISO = "2026-05-23T12:00:00+00:00"
_FROZEN_EXPIRES_AT = 1900000000.0  # far-future epoch; never triggers refresh
_FROZEN_ENTRY_ID = "01TESTDIAGNOSTICSENTRYID001"


@pytest.fixture(name="expires_at")
def fixture_deterministic_expires_at() -> float:
    """Override the conftest ``expires_at`` fixture with a fixed timestamp.

    The conftest default is ``time.time() + 86400`` — fine for non-snapshot
    tests, but it churns the diagnostics snapshot's ``token_metadata.expires_at``
    field. Pinning it here keeps the snapshot stable across runs.
    """
    return _FROZEN_EXPIRES_AT


# Distinctive sentinel strings — high-entropy enough that an accidental
# substring collision with structural keys ("token", "data", etc.) won't
# trigger false positives.
_SENTINEL_ACCESS_TOKEN = "SENTINEL_ACCESS_TOKEN_DO_NOT_LEAK"
_SENTINEL_REFRESH_TOKEN = "SENTINEL_REFRESH_TOKEN_DO_NOT_LEAK"
_SENTINEL_ID_TOKEN = "SENTINEL_ID_TOKEN_DO_NOT_LEAK"
_SENTINEL_DISPLAY_NAME = "SENTINEL_DISPLAY_NAME_DO_NOT_LEAK"

# Distinctive numeric sentinels for the telemetry-PII test. Chosen so
# they don't collide with legitimate vehicle ids, listener counts, expires_at
# epoch values, or any other small-integer / large-int field surfaced by the
# diagnostics shape.
_SENTINEL_GPS_LAT = 99.123456
_SENTINEL_GPS_LONG = 99.234567
_SENTINEL_ODOMETER = 999_999_999
_SENTINEL_SPEED_KPH = 123_456

_VEHICLE_A = AbrpVehicle(
    vehicle_id=MOCK_VEHICLE_ID,
    name=MOCK_VEHICLE_NAME,
    vehicle_model=MOCK_VEHICLE_MODEL,
    paint=None,
)
_VEHICLE_B = AbrpVehicle(
    vehicle_id=MOCK_VEHICLE_ID_2,
    name=MOCK_VEHICLE_NAME_2,
    vehicle_model=MOCK_VEHICLE_MODEL_2,
    paint=None,
)


async def _setup_integration(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockConfigEntry:
    """Register the integration's OAuth implementation and set up the entry.

    Accepts the 0.5 s real-time pre-warm sleep — see
    ``project_abrp_asyncio_sleep_test_patching`` for the rationale.
    """
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _build_entry(
    token_entry: dict[str, Any],
    *,
    vehicle_ids: list[str],
    known_vehicle_ids: list[str],
    entry_id: str | None = None,
) -> MockConfigEntry:
    """Build a ``MockConfigEntry`` with both VEHICLE_IDS and KNOWN_VEHICLE_IDS set.

    Both fields are explicit because diagnostics surfaces the declined-set
    as ``known - selected``; tests need control over both ends.

    Pass ``entry_id`` to pin a deterministic id for snapshot tests —
    ``MockConfigEntry`` generates a fresh ULID per run otherwise, which
    would churn the diagnostics snapshot's ``entry_id`` field on every
    run.
    """
    kwargs: dict[str, Any] = {
        "domain": DOMAIN,
        "unique_id": SENSOR_TEST_SUB,
        "data": {
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: vehicle_ids,
            CONF_KNOWN_VEHICLE_IDS: known_vehicle_ids,
        },
    }
    if entry_id is not None:
        kwargs["entry_id"] = entry_id
    return MockConfigEntry(**kwargs)


# ---------------------------------------------------------------------------
# Snapshot smoke
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_sse_client", "mock_seed_responses")
async def test_diagnostics_snapshot(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """The diagnostics payload matches the locked Syrupy snapshot.

    Setup: two vehicles in the garage; VEHICLE_IDS selects only A (B is in
    KNOWN but not in VEHICLE_IDS — i.e. declined).  One SSE telemetry frame
    is applied for A so ``_presence_seen`` is non-empty and the
    ``telemetry`` block has content.

    Snapshot at ``snapshots/test_diagnostics.ambr``.  This is the primary
    *shape* oracle — any deliberate change to the diagnostics dict shape
    requires a snapshot refresh; an accidental change fails this test
    loudly.

    Deterministic-snapshot strategy: setup runs under the real clock to
    avoid breaking ``hass_client`` 's bearer-token validation. Post-setup,
    we overwrite the two natively-stamped timestamp fields on the runtime
    coordinators (``garage_coordinator.last_update_success_time`` and
    ``telemetry_coordinator.sse_state["last_connect_at"]``) plus pin
    ``entry_id`` and ``expires_at`` to fixed values. The snapshot
    therefore pins the *shape* of the dict, not the timestamp-generation
    behavior (which is exercised by the framework's own
    ``DataUpdateCoordinator`` tests, not relitigated here).
    """
    entry = _build_entry(
        token_entry,
        vehicle_ids=[str(MOCK_VEHICLE_ID)],
        known_vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        entry_id=_FROZEN_ENTRY_ID,
    )
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]
    await _setup_integration(hass, entry)

    runtime_data: AbrpData = entry.runtime_data
    runtime_data.telemetry_coordinator.apply_frame(
        build_telemetry_frame(MOCK_VEHICLE_ID, soc=0.42)
    )
    await hass.async_block_till_done()

    # Pin the natively-stamped timestamp fields post-setup so the snapshot
    # is reproducible. Both coordinators carry ``last_update_success_time``
    # (an attribute on ``TimestampDataUpdateCoordinator``) — the garage one
    # is set by the polling-refresh path; the telemetry one is set by
    # ``apply_frame`` (stays ``None`` until the first frame arrives, so
    # this overwrite is robust against an unstarted stream).
    # ``sse_state["last_connect_at"]``
    # is a mutable dict on the telemetry coordinator updated by the SSE
    # loop. The diagnostics module reads all three at call time, so
    # overwriting after setup is sufficient.
    runtime_data.garage_coordinator.last_update_success_time = _FROZEN_LAST_UPDATE_TIME
    runtime_data.telemetry_coordinator.last_update_success_time = (
        _FROZEN_LAST_UPDATE_TIME
    )
    # ``last_attempt_at`` is stamped at every connect attempt, so it
    # picks up wall-clock during setup; pin it for the same reason
    # ``last_connect_at`` is pinned. Pin ``connected`` and ``connect_count``
    # to representative post-first-frame values so the snapshot reflects a
    # working installation rather than the pre-frame transient.
    runtime_data.telemetry_coordinator.sse_state["last_attempt_at"] = (
        _FROZEN_LAST_CONNECT_ISO
    )
    runtime_data.telemetry_coordinator.sse_state["last_connect_at"] = (
        _FROZEN_LAST_CONNECT_ISO
    )
    runtime_data.telemetry_coordinator.sse_state["connected"] = True
    runtime_data.telemetry_coordinator.sse_state["connect_count"] = 1

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diagnostics == snapshot


# ---------------------------------------------------------------------------
# Load-bearing redaction oracle
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_sse_client", "mock_seed_responses")
async def test_diagnostics_no_secrets_leak(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_abrp_client: AsyncMock,
) -> None:
    """No sentinel from ``access_token`` / ``refresh_token`` / ``id_token`` leaks.

    Builds an entry whose OAuth token block contains three distinctive
    sentinel strings, calls diagnostics, JSON-serialises the result, and
    asserts NONE of the sentinels appear anywhere in the serialised
    output.  Catches any future field added to the diagnostics dict that
    bypasses ``async_redact_data`` on the token subtree (e.g. surfacing
    ``entry.data["token"]`` raw alongside a redacted copy, leaking the
    decoded id_token claims unredacted, etc.).

    The id_token is not parsed as a valid JWT (the sentinel value isn't
    a real base64-encoded JSON payload) — that's deliberate.
    ``_decode_id_token_claims`` is best-effort and returns ``None`` on
    invalid input, so this test focuses on the raw-token-subtree
    redaction.  A complementary test could be added later for the
    decoded-claims-redaction path.
    """
    sentinel_token: dict[str, Any] = {
        "access_token": _SENTINEL_ACCESS_TOKEN,
        "refresh_token": _SENTINEL_REFRESH_TOKEN,
        "token_type": "Bearer",
        "expires_at": 9_999_999_999.0,
        "id_token": _SENTINEL_ID_TOKEN,
    }
    entry = _build_entry(
        sentinel_token,
        vehicle_ids=[str(MOCK_VEHICLE_ID)],
        known_vehicle_ids=[str(MOCK_VEHICLE_ID)],
    )
    mock_abrp_client.return_value = [_VEHICLE_A]
    await _setup_integration(hass, entry)

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    serialised = json.dumps(diagnostics)

    assert _SENTINEL_ACCESS_TOKEN not in serialised, (
        "access_token leaked through diagnostics — TO_REDACT bypass?"
    )
    assert _SENTINEL_REFRESH_TOKEN not in serialised, (
        "refresh_token leaked through diagnostics — TO_REDACT bypass?"
    )
    assert _SENTINEL_ID_TOKEN not in serialised, (
        "raw id_token leaked through diagnostics — TO_REDACT bypass?"
    )


# ---------------------------------------------------------------------------
# Presence-seen / predicate-registration oracle
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_sse_client", "mock_seed_responses")
async def test_diagnostics_presence_state_reflects_seen_set(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
) -> None:
    """``presence_seen`` reflects applied frames; ``presence_predicates`` locks the registration shape.

    Setup: both vehicles selected, empty JSON seed (default
    ``mock_seed_responses`` returns ``{}`` per vehicle → no eager
    telemetry-sensor creation → ``_presence_seen`` starts empty after
    setup).  Then drive two ``apply_frame`` calls:

    * Vehicle A → ``soc = 0.55`` (frame routed through the dispatcher
      → sensor platform's ``_on_new_metric`` → ``mark_metric_seen`` for
      ``(A, "soc")``).
    * Vehicle B → ``power = 1500`` (same path, marks ``(B, "power")``).

    Assertions:

    * ``presence_seen`` is exactly ``[[A, "soc"], [B, "power"]]`` sorted.
    * ``presence_predicates`` is exactly ``["power", "soc", "voltage"]``
      — the keys from ``SENSORS`` in ``sensor.py``.

    Key paths are nested under ``result["telemetry_coordinator"]`` as
    ``presence_seen`` and ``presence_predicates_registered`` (note the
    ``_registered`` suffix).
    """
    entry = _build_entry(
        token_entry,
        vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        known_vehicle_ids=[str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
    )
    mock_abrp_client.return_value = [_VEHICLE_A, _VEHICLE_B]
    await _setup_integration(hass, entry)

    runtime_data: AbrpData = entry.runtime_data
    runtime_data.telemetry_coordinator.apply_frame(
        build_telemetry_frame(MOCK_VEHICLE_ID, soc=0.55)
    )
    runtime_data.telemetry_coordinator.apply_frame(
        build_telemetry_frame(MOCK_VEHICLE_ID_2, power=1500.0)
    )
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    telemetry_block = diagnostics["telemetry_coordinator"]
    # Set comparison: the diagnostics dict surfaces ``presence_seen`` as a
    # list, but the pair-ordering is not part of the semantic contract
    # (the underlying ``_presence_seen`` is a set; any list-ordering it
    # happens to produce is an implementation detail). Comparing as a
    # set decouples the oracle from accidental ordering shifts.
    assert {tuple(pair) for pair in telemetry_block["presence_seen"]} == {
        (MOCK_VEHICLE_ID, "soc"),
        (MOCK_VEHICLE_ID_2, "power"),
    }
    assert telemetry_block["presence_predicates_registered"] == [
        "battery_capacity",
        "battery_temperature",
        "calibrated_ref_cons",
        "charging_state",
        "odometer",
        "power",
        "range",
        "soc",
        "soe",
        "soh",
        "voltage",
    ]


# ---------------------------------------------------------------------------
# Regression: no display-name PII leak via entry.title
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_sse_client", "mock_seed_responses")
async def test_diagnostics_no_title_pii_leak(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
) -> None:
    """``entry.title`` must not leak the display-name claim.

    Background: the entry title is built as
    ``f"{flow_impl.name} ({display_name})"`` where ``display_name`` is the
    OIDC ``name`` (or ``email`` fallback) claim from the id_token. That
    string can carry PII — first names, full names, email-like strings.
    Diagnostics serialises ``entry.title`` verbatim into the dump unless
    a redaction path is in place.

    Builds a ``MockConfigEntry`` whose ``title`` carries a distinctive
    sentinel string, calls diagnostics, JSON-serialises the result, and
    asserts the sentinel does NOT appear anywhere in the serialised
    output. The fix can be either redacting ``title`` in the entry
    block, stripping the parenthetical, or dropping the title from
    diagnostics entirely — any of those satisfies the oracle.
    """
    leaky_title = f"A Better Routeplanner ({_SENTINEL_DISPLAY_NAME})"
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        title=leaky_title,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [str(MOCK_VEHICLE_ID)],
            CONF_KNOWN_VEHICLE_IDS: [str(MOCK_VEHICLE_ID)],
        },
    )
    mock_abrp_client.return_value = [_VEHICLE_A]
    await _setup_integration(hass, entry)

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    serialised = json.dumps(diagnostics)

    assert _SENTINEL_DISPLAY_NAME not in serialised, (
        "display-name PII leaked via entry.title"
    )


# ---------------------------------------------------------------------------
# Regression: no GPS / odometer / speed PII leak via telemetry
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_sse_client", "mock_seed_responses")
async def test_diagnostics_no_telemetry_pii_leak(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
) -> None:
    """Position / odometer / speed must not leak verbatim.

    Background: ``apply_frame`` is a permissive shallow-merge — any
    non-None key in the frame gets stored in ``coordinator.data``. The
    diagnostics dump surfaces ``telemetry`` verbatim unless a redaction
    path filters it. GPS coordinates (``location.lat``,
    ``location.long``), odometer readings, and speed values all carry
    user PII / trip-history risk if a future SSE schema bump adds those
    keys.

    Drives ``apply_frame`` with a frame carrying three distinctive
    sentinel values (``location.lat = 99.123456``,
    ``odometer.m = 999_999_999``, ``speed.kph = 123_456`` — chosen so
    they cannot collide with legitimate vehicle ids, counts, or
    timestamps). Calls diagnostics, JSON-serialises, asserts none of the
    sentinel values appear anywhere.

    Either fix path satisfies the oracle:
    * Filter unknown / sensitive keys at ``apply_frame`` time so they
      never enter ``coordinator.data``.
    * Add ``"location"`` / ``"odometer"`` / ``"speed"`` to ``TO_REDACT``
      (or a per-telemetry-key redaction pass) in ``diagnostics.py``.
    """
    entry = _build_entry(
        token_entry,
        vehicle_ids=[str(MOCK_VEHICLE_ID)],
        known_vehicle_ids=[str(MOCK_VEHICLE_ID)],
    )
    mock_abrp_client.return_value = [_VEHICLE_A]
    await _setup_integration(hass, entry)

    runtime_data: AbrpData = entry.runtime_data
    leaky_frame: dict[str, Any] = {
        "vehicleId": MOCK_VEHICLE_ID,
        "location": {"lat": _SENTINEL_GPS_LAT, "long": _SENTINEL_GPS_LONG},
        "odometer": {"m": _SENTINEL_ODOMETER},
        "speed": {"kph": _SENTINEL_SPEED_KPH},
    }
    runtime_data.telemetry_coordinator.apply_frame(leaky_frame)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    serialised = json.dumps(diagnostics)

    assert str(_SENTINEL_GPS_LAT) not in serialised, (
        "GPS latitude leaked through telemetry block"
    )
    assert str(_SENTINEL_GPS_LONG) not in serialised, (
        "GPS longitude leaked through telemetry block"
    )
    assert str(_SENTINEL_ODOMETER) not in serialised, (
        "odometer reading leaked through telemetry block"
    )
    assert str(_SENTINEL_SPEED_KPH) not in serialised, (
        "speed value leaked through telemetry block"
    )


# ---------------------------------------------------------------------------
# Regression: apply_frame updates last_update_success_time
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_sse_client", "mock_seed_responses")
async def test_diagnostics_telemetry_last_update_success_time_updates_on_apply_frame(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
) -> None:
    """``apply_frame`` must stamp ``last_update_success_time``.

    Background: ``AbrpTelemetryCoordinator`` extends
    ``TimestampDataUpdateCoordinator``, which carries a
    ``last_update_success_time`` attribute set by the polling-refresh
    path (``_async_refresh_finished``). The telemetry coordinator doesn't
    poll — frames arrive via SSE and are merged through
    ``apply_frame`` / ``async_set_updated_data``. The framework
    attribute is never updated by that path, so it stays ``None``
    forever and the diagnostics ``telemetry_coordinator.last_update_success_time``
    field misleadingly reports "no successful update" despite a healthy
    stream.

    The fix: explicitly set ``self.last_update_success_time = utcnow()``
    in ``apply_frame`` (or use a framework API that does so).

    Sequence — drives ``apply_frame`` at two distinct frozen-clock
    instants and asserts the attribute tracks each:

    1. ``freeze_time(T1):`` ``apply_frame(soc=0.5)``. Assert
       ``last_update_success_time == T1``.
    2. ``freeze_time(T2):`` ``apply_frame(soc=0.6)``. Assert
       ``last_update_success_time == T2`` (updates on EVERY frame, not
       just the first).

    The original draft of this test had a step-zero "pre-frame" assertion
    that ``last_update_success_time is None`` after setup. That
    assumption was wrong: ``async_seed_from_json_poll`` calls
    ``apply_frame`` once per selected vehicle even when the seed
    response is empty (the frame is ``{"vehicleId": vid}``), so the
    field is already stamped by the time setup returns. The pre-frame
    assertion is redundant anyway — the t1 → t2 transitions are the
    load-bearing oracle: if ``apply_frame`` doesn't stamp, step 1's
    ``None == t1`` (or ``some-other-time == t1``) fails; if it stamps
    only the first frame, step 2 fails when t1 doesn't advance to t2.

    Uses ``freeze_time`` as a context manager rather than the
    ``freezer`` fixture — the fixture freezes the clock at
    fixture-creation time (BEFORE the test body runs), which would
    deadlock the ``asyncio.sleep(PREWARM_WINDOW_SECONDS)`` in
    ``async_setup_entry``. The context manager defers the freeze to
    after setup completes.

    No ``hass_client`` involvement — the assertion is on the coordinator
    attribute directly.

    Catches: ``apply_frame`` regression that drops the timestamp stamp
    (step 1 fails); regression that stamps only on first frame
    (step 2 fails); regression that stamps with the wrong time source
    (either step fails).
    """
    entry = _build_entry(
        token_entry,
        vehicle_ids=[str(MOCK_VEHICLE_ID)],
        known_vehicle_ids=[str(MOCK_VEHICLE_ID)],
    )
    mock_abrp_client.return_value = [_VEHICLE_A]
    await _setup_integration(hass, entry)

    runtime_data: AbrpData = entry.runtime_data
    telemetry = runtime_data.telemetry_coordinator

    t1 = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)
    with freeze_time(t1):
        telemetry.apply_frame(build_telemetry_frame(MOCK_VEHICLE_ID, soc=0.5))
    assert telemetry.last_update_success_time == t1

    t2 = datetime(2026, 5, 23, 12, 5, 0, tzinfo=UTC)
    with freeze_time(t2):
        telemetry.apply_frame(build_telemetry_frame(MOCK_VEHICLE_ID, soc=0.6))
    assert telemetry.last_update_success_time == t2


# ---------------------------------------------------------------------------
# Providers block on telemetry_coordinator diagnostics
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_sse_client", "mock_seed_responses")
async def test_diagnostics_providers_block_reflects_stamped_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
) -> None:
    """``telemetry_coordinator.providers`` surfaces stamped per-vehicle providers.

    Behavioral oracle for the providers diagnostics extension — kept
    separate from the snapshot test so the snapshot doesn't need to
    regenerate when the providers block evolves. Drives one apply_frame
    with a per-metric provider and asserts the diagnostics dict shape
    reflects it.

    Providers are a public enum (no PII), so they pass through verbatim
    (no redaction). The existing
    ``test_diagnostics_no_telemetry_pii_leak`` covers the symmetric
    contract — if a future change accidentally surfaced raw lat/long
    inside the providers block instead of enum strings, that test would
    catch it.
    """
    entry = _build_entry(
        token_entry,
        vehicle_ids=[str(MOCK_VEHICLE_ID)],
        known_vehicle_ids=[str(MOCK_VEHICLE_ID)],
    )
    mock_abrp_client.return_value = [_VEHICLE_A]
    await _setup_integration(hass, entry)

    runtime_data: AbrpData = entry.runtime_data
    runtime_data.telemetry_coordinator.apply_frame(
        {
            "vehicleId": MOCK_VEHICLE_ID,
            "soc": {"frac": 0.42, "provider": "RIVIAN_STREAM"},
        }
    )
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    telemetry_block = diagnostics["telemetry_coordinator"]

    assert telemetry_block["providers"] == {
        str(MOCK_VEHICLE_ID): {
            "soc": "RIVIAN_STREAM",
        },
    }
