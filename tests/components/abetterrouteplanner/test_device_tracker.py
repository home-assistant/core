"""Tests for the device_tracker platform.

GPS location is exposed as a single ``device_tracker`` entity per
vehicle (NOT a pair of lat/long sensors). Entities are lazy-created via
the dispatcher pattern — registered only after a frame arrives
with valid ``location.lat`` + ``location.long``.

Tests observe via the entity_registry / hass.states surface; no direct
import of ``device_tracker.py`` is required, so the file imports
cleanly even when the platform module is refactored.

Lookup uses ``entity_registry.async_get_entity_id("device_tracker",
DOMAIN, unique_id)`` against the unique_id shape
``f"{entry.unique_id}_{vehicle_id}_location"`` — keeps assertions
decoupled from the integration's ``strings.json`` slug choice.
"""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.abetterrouteplanner import AbrpData
from homeassistant.components.abetterrouteplanner.const import CONF_VEHICLE_IDS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2, SENSOR_TEST_SUB

from tests.common import MockConfigEntry


def _location_unique_id(vehicle_id: int) -> str:
    """Return the planned ``device_tracker`` unique_id for ``vehicle_id``.

    Mirrors the ``__init__`` body:
    ``self._attr_unique_id = f"{scope}_location"`` where ``scope ==
    f"{entry.unique_id}_{vehicle.vehicle_id}"``. Pinning the format here
    means a future rename of the unique_id surfaces as a clean test
    failure instead of a silent miss.
    """
    return f"{SENSOR_TEST_SUB}_{vehicle_id}_location"


def _push_frame(entry: MockConfigEntry, frame: dict[str, Any]) -> None:
    """Inject a synthesized telemetry frame at the coordinator boundary."""
    runtime_data: AbrpData = entry.runtime_data
    runtime_data.telemetry_coordinator.apply_frame(frame)


async def _lazy_setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the integration with the pre-warm window collapsed to zero.

    Patches ``PREWARM_WINDOW_SECONDS`` (not ``asyncio.sleep``) so the SSE
    retry backoff loop keeps using a real sleep.
    """
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.abetterrouteplanner.PREWARM_WINDOW_SECONDS",
        0,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


def _find_location_entity_id(
    entity_registry: er.EntityRegistry, vehicle_id: int
) -> str | None:
    """Return the registered ``device_tracker`` entity_id for ``vehicle_id``."""
    return entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, _location_unique_id(vehicle_id)
    )


def _location_frame(
    vehicle_id: int, lat: float, lng: float, **extra: Any
) -> dict[str, Any]:
    """Build a wire-shape frame with a ``location`` block.

    ``extra`` lets a test merge non-location metrics into the same
    frame (e.g. exercising the merged predicate-registration path
    without inflating ``build_telemetry_frame`` for the conftest).
    """
    return {
        "vehicleId": vehicle_id,
        "location": {"lat": lat, "long": lng},
        **extra,
    }


# ---------------------------------------------------------------------------
# Lazy-creation: device_tracker only registers once location data arrives
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_device_tracker_created_when_location_present_at_setup(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """A seed containing ``location.{lat,long}`` registers the tracker eagerly.

    Setup-time inspection path: the platform reads
    ``telemetry_coordinator.data`` after the JSON seed + pre-warm window
    and registers exactly those entities whose predicate returns
    non-None. ``_extract_lat_long`` is the location predicate; a frame
    with both inner keys present satisfies it.

    Will-fail oracle: without ``device_tracker.py`` the platform never
    forwards and the unique_id lookup returns None.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {
        "location": {"lat": 37.7749, "long": -122.4194},
    }

    await _lazy_setup(hass, config_entry_with_vehicles)

    entity_id = _find_location_entity_id(entity_registry, MOCK_VEHICLE_ID)
    assert entity_id is not None, (
        "device_tracker.<vehicle>_location must register from seed-time location"
    )


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_device_tracker_lazy_created_on_first_location_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Empty seed → no tracker; an SSE-arrived location frame creates it.

    Pins the dispatcher path: after setup the tracker does NOT exist;
    pushing a frame with ``location.{lat,long}`` fires the
    ``signal_new_metric`` dispatcher, which the device_tracker platform's
    ``_on_new_metric`` listener handles to call ``async_add_entities``.

    presence must be
    evaluated by the predicate (``_extract_lat_long``), not raw payload
    key presence — a key-level dispatcher would silently freeze the
    entity if the first frame had ``location: {time: ...}`` only.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert _find_location_entity_id(entity_registry, MOCK_VEHICLE_ID) is None

    _push_frame(
        config_entry_with_vehicles,
        _location_frame(MOCK_VEHICLE_ID, lat=51.5074, lng=-0.1278),
    )
    await hass.async_block_till_done()

    entity_id = _find_location_entity_id(entity_registry, MOCK_VEHICLE_ID)
    assert entity_id is not None


# ---------------------------------------------------------------------------
# Observable state: latitude/longitude track the merged frame
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_device_tracker_latitude_longitude_track_merged_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """``.latitude`` / ``.longitude`` reflect the latest merged frame.

    Subsequent frames merge into the coordinator's per-vehicle map.
    The device_tracker entity reads ``coordinator.data[vehicle_id]`` on
    every state read, so the lat/long attributes track the merged
    snapshot — including null-leaf partial updates (a frame carrying
    ``{lat: X, long: null}`` keeps the prior long).

    Observable surface: ``hass.states.get(entity_id).attributes`` carries
    the rendered latitude/longitude.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    _push_frame(
        config_entry_with_vehicles,
        _location_frame(MOCK_VEHICLE_ID, lat=37.7749, lng=-122.4194),
    )
    await hass.async_block_till_done()

    entity_id = _find_location_entity_id(entity_registry, MOCK_VEHICLE_ID)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["latitude"] == pytest.approx(37.7749)
    assert state.attributes["longitude"] == pytest.approx(-122.4194)

    _push_frame(
        config_entry_with_vehicles,
        _location_frame(MOCK_VEHICLE_ID, lat=40.7128, lng=-74.0060),
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["latitude"] == pytest.approx(40.7128)
    assert state.attributes["longitude"] == pytest.approx(-74.0060)


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_device_tracker_source_type_is_gps(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """The tracker reports ``source_type == gps``.

    GPS-only device_tracker; not the lat/long-sensors alternative.
    The ``source_type`` attribute pins this contract at the state
    surface — a developer who accidentally returns ``SourceType.ROUTER``
    or similar trips this assertion.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {
        "location": {"lat": 37.7749, "long": -122.4194},
    }

    await _lazy_setup(hass, config_entry_with_vehicles)

    entity_id = _find_location_entity_id(entity_registry, MOCK_VEHICLE_ID)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["source_type"] == "gps"


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_location_entity_is_not_diagnostic_category(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """The device_tracker is primary (entity_category is None), not Diagnostic.

    HA's ``BaseTrackerEntity`` default at
    ``homeassistant/components/device_tracker/config_entry.py:176`` sets
    ``_attr_entity_category = EntityCategory.DIAGNOSTIC``. For an EV the
    live location IS the primary user-facing surface; ABRP overrides
    this default to ``None`` so the tracker surfaces on the main
    dashboard rather than the diagnostic section.

    ``entity_category`` is a registry-options field, not a state
    attribute — assert via ``entity_registry.async_get(...)``.

    ``AbrpDeviceTracker`` sets ``_attr_entity_category = None`` to
    override the framework default of ``EntityCategory.DIAGNOSTIC``.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {
        "location": {"lat": 37.7749, "long": -122.4194},
    }

    await _lazy_setup(hass, config_entry_with_vehicles)

    entity_id = _find_location_entity_id(entity_registry, MOCK_VEHICLE_ID)
    assert entity_id is not None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.entity_category is None


# ---------------------------------------------------------------------------
# Negation oracles: presence-trap variants must not create the entity
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
@pytest.mark.parametrize(
    "location_payload",
    [
        pytest.param({"time": 12345}, id="time_only_no_lat_long"),
        pytest.param({"lat": 37.7749}, id="lat_only_missing_long"),
        pytest.param({"long": -122.4194}, id="long_only_missing_lat"),
        pytest.param({"lat": "bogus", "long": -122.4}, id="lat_is_string"),
        pytest.param({"lat": True, "long": -122.4}, id="lat_is_bool"),
        pytest.param({"lat": 37.77, "long": True}, id="long_is_bool"),
    ],
)
async def test_device_tracker_not_created_for_invalid_location_shapes(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
    location_payload: dict[str, Any],
) -> None:
    """Predicate-rejected shapes must NOT lazy-create the tracker.

    Adversarial-input pass:

    * ``location: {time: ...}`` — neither lat nor long → None ✅
    * ``location: {lat: X}`` (missing long) — partial → None ✅
    * ``location: {lat: "bogus"}`` — wrong type → None ✅
    * ``location: {lat: True}`` — bool-isinstance trap (bool ⊂ int in
      Python; ``isinstance(True, (int, float))`` is True!) → exclude
      explicitly ✅

    presence is
    predicate-evaluated, not raw-key-present. A frame with a partial
    location MUST NOT register the entity, otherwise the next frame
    with valid coords gets suppressed by the ``_presence_seen`` guard.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    _push_frame(
        config_entry_with_vehicles,
        {"vehicleId": MOCK_VEHICLE_ID, "location": location_payload},
    )
    await hass.async_block_till_done()

    assert _find_location_entity_id(entity_registry, MOCK_VEHICLE_ID) is None


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_device_tracker_recovers_after_partial_then_full_location(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """A partial ``location.{time}`` frame must not freeze a later full frame.

    Direct analogue of the ``test_soc_time_only_then_frac_regression``
    test for the existing soc metric — the lazy/dispatcher contract
    must keep dispatching for the metric until the predicate first
    returns non-None.

    Two-frame sequence:

    1. ``location: {time: 12345}`` → predicate None → entity NOT created
       AND ``_presence_seen`` for this ``(vehicle, location)`` NOT
       marked.
    2. ``location: {lat: X, long: Y}`` → predicate non-None →
       dispatcher fires → entity created.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    _push_frame(
        config_entry_with_vehicles,
        {"vehicleId": MOCK_VEHICLE_ID, "location": {"time": 12345}},
    )
    await hass.async_block_till_done()
    assert _find_location_entity_id(entity_registry, MOCK_VEHICLE_ID) is None

    _push_frame(
        config_entry_with_vehicles,
        _location_frame(MOCK_VEHICLE_ID, lat=48.8566, lng=2.3522),
    )
    await hass.async_block_till_done()

    entity_id = _find_location_entity_id(entity_registry, MOCK_VEHICLE_ID)
    assert entity_id is not None


# ---------------------------------------------------------------------------
# Multi-vehicle isolation
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_device_tracker_multi_vehicle_isolation(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """A location frame for vehicle A must not create vehicle B's tracker.

    Both vehicles selected; only vehicle A receives a location frame.
    Vehicle B remains track-less even though both are selected and
    in-garage. Confirms the per-vehicle predicate evaluation in
    ``apply_frame`` does not bleed across vehicle ids.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        },
    )
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}
    mock_seed_responses.responses[MOCK_VEHICLE_ID_2] = {}

    await _lazy_setup(hass, entry)

    _push_frame(
        entry,
        _location_frame(MOCK_VEHICLE_ID, lat=37.7749, lng=-122.4194),
    )
    await hass.async_block_till_done()

    assert _find_location_entity_id(entity_registry, MOCK_VEHICLE_ID) is not None
    assert _find_location_entity_id(entity_registry, MOCK_VEHICLE_ID_2) is None


# ---------------------------------------------------------------------------
# Coverage pin: sensor predicates (soc/power/voltage/soe/odometer)
# survive when device_tracker's location predicate is also registered.
# Pins ``register_presence_predicates`` merge-mode semantics.
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_sensor_predicates_survive_device_tracker_registration(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Sensor + device_tracker register predicates independently — both fire.

    ``register_presence_predicates`` lets each platform contribute its
    own keys without clobbering siblings. Observable proof: with an
    empty seed, push a frame carrying BOTH ``soc.frac`` (sensor
    predicate) AND ``location.{lat,long}`` (device_tracker predicate)
    — both entities must lazy-create.

    Would fail if the device_tracker's register call overwrote the
    sensor platform's earlier registration (or vice-versa).

    Lookup uses unique_id pattern (decoupled from strings.json choices)
    for both entity_ids.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    _push_frame(
        config_entry_with_vehicles,
        {
            "vehicleId": MOCK_VEHICLE_ID,
            "soc": {"frac": 0.5},
            "location": {"lat": 37.7749, "long": -122.4194},
        },
    )
    await hass.async_block_till_done()

    soc_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SENSOR_TEST_SUB}_{MOCK_VEHICLE_ID}_soc"
    )
    assert soc_entity_id is not None, "soc sensor must still lazy-create"
    location_entity_id = _find_location_entity_id(entity_registry, MOCK_VEHICLE_ID)
    assert location_entity_id is not None, "device_tracker must lazy-create"
