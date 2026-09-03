"""Tests for sensor state restoration across HA restart."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

from aioabrp import AbrpVehicle, Telemetry
from freezegun import freeze_time
import pytest

from homeassistant.components.abetterrouteplanner.const import DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, STATE_UNAVAILABLE
from homeassistant.core import CoreState, HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_PAINT,
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    MOCK_VEHICLE_MODEL,
    MOCK_VEHICLE_NAME,
    SENSOR_TEST_SUB,
    build_metric_value,
)

from tests.common import MockConfigEntry, mock_restore_cache_with_extra_data

VOLTAGE_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_voltage"

# Sentinel for "omit ``provider``", distinct from a present-but-null ``None``.
_PROVIDER_UNSET: Any = object()

RESTORED_PROVIDER = "RIVIAN_STREAM"

# Times chosen to stay visibly disjoint from the per-frame-stamp test's ranges.
RESTORED_VOLTAGE = 410.0
RESTORED_STAMP_ISO = "2026-05-20T12:00:00+00:00"
RESTORED_STAMP_DT = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)

# Object-id stems matching each mock vehicle's name, so the restore cache
# (keyed by entity_id) hits instead of falling back to the auto-slug.
_OBJECT_ID_STEM = {
    MOCK_VEHICLE_ID: "rivian_r2_2027_standard_long_range",
    MOCK_VEHICLE_ID_2: "rivian_r1s_2024_quad_max",
}


def _fire_voltage(
    entry: MockConfigEntry,
    fake_stream: Any,
    voltage: float,
    *,
    provider: str | None = None,
) -> None:
    """Drive a single-voltage live frame through the fake telemetry stream."""
    assert entry.runtime_data is not None  # entry set up before firing.
    fake_stream.fire_frame(
        MOCK_VEHICLE_ID,
        Telemetry(voltage=build_metric_value(voltage, provider=provider)),
    )


def _voltage_restored_state(
    *,
    native_value: float | None = RESTORED_VOLTAGE,
    last_reported_at: str | None = RESTORED_STAMP_ISO,
    provider: Any = _PROVIDER_UNSET,
) -> tuple[State, dict[str, Any]]:
    """Build a (State, extra_data) tuple for ``mock_restore_cache_with_extra_data``.

    The staleness metadata is seeded only into the extra data, never into the
    state attributes, so these tests fail if the entity ever reads it back from
    attributes — a channel HA drops while an entity is unavailable.
    """
    state = State(
        VOLTAGE_ENTITY_ID,
        str(native_value) if native_value is not None else "unknown",
    )
    extra_data: dict[str, Any] = {
        "native_value": native_value,
        "native_unit_of_measurement": "V",
        "last_reported_at": last_reported_at,
        "provider": None if provider is _PROVIDER_UNSET else provider,
    }
    return state, extra_data


async def _restart_setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    *,
    entity_registry: er.EntityRegistry | None = None,
    preseed_registry_keys: list[str] | None = None,
    preseed_vehicle_ids: tuple[int, ...] = (MOCK_VEHICLE_ID,),
    restored_states: list[tuple[State, dict[str, Any]]] | None = None,
) -> None:
    """Set up the integration simulating an HA restart with optional prior state."""
    hass.set_state(CoreState.not_running)
    if restored_states is not None:
        mock_restore_cache_with_extra_data(hass, restored_states)
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    if preseed_registry_keys and entity_registry is not None:
        for vehicle_id in preseed_vehicle_ids:
            for key in preseed_registry_keys:
                # Without this the auto-slug is ``f"{platform}_{unique_id}"`` and
                # the restore cache, keyed by entity_id, misses.
                entity_registry.async_get_or_create(
                    domain="sensor",
                    platform=DOMAIN,
                    unique_id=f"{SENSOR_TEST_SUB}_{vehicle_id}_{key}",
                    config_entry=entry,
                    suggested_object_id=f"{_OBJECT_ID_STEM[vehicle_id]}_{key}",
                )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_cold_install_lazy_create_preserved(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """Cold install: no registry, no seed, no frame → no entity yet; frame creates."""

    await _restart_setup(hass, config_entry_with_vehicles)

    assert hass.states.get(VOLTAGE_ENTITY_ID) is None

    _fire_voltage(config_entry_with_vehicles, fake_stream, 400.0)
    await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.state == "400.0"


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_restart_eager_create_from_registry(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """Prior voltage registry entry → entity eager-created BEFORE any frame."""

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
    )

    # The contract is state-exists, not state-has-value.
    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None


@pytest.mark.parametrize(
    ("live_voltage", "expected_state"),
    [
        pytest.param(
            None, str(RESTORED_VOLTAGE), id="restored_only_before_first_frame"
        ),
        pytest.param(420.0, "420.0", id="live_frame_overwrites_restored"),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_restore_native_value_then_optional_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
    live_voltage: float | None,
    expected_state: str,
) -> None:
    """Restored native_value persists; a live voltage frame overrides it."""

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
        restored_states=[_voltage_restored_state()],
    )

    if live_voltage is not None:
        _fire_voltage(config_entry_with_vehicles, fake_stream, live_voltage)
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_restore_last_reported_at_round_trips_as_datetime(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """Restored ISO ``last_reported_at`` parses back to ``datetime`` on the entity."""

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
        restored_states=[_voltage_restored_state()],
    )

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    stamp = state.attributes.get("last_reported_at")
    assert isinstance(stamp, datetime)
    assert stamp == RESTORED_STAMP_DT


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_malformed_restored_stamp_omits_attribute(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """Malformed stamp → ``last_reported_at`` ABSENT from attributes (not None)."""

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
        restored_states=[_voltage_restored_state(last_reported_at="banana")],
    )

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.state == str(RESTORED_VOLTAGE)
    # Absent, not None: omit-on-failure beats propagating a null.
    assert "last_reported_at" not in state.attributes


@pytest.mark.usefixtures("mock_abrp_client")
async def test_last_reported_at_stamps_per_metric_not_per_merged_state(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """Stamp refreshes only on frames whose batch carries the voltage metric."""

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
    )

    t1 = datetime(2026, 5, 24, 10, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 5, 24, 10, 5, 0, tzinfo=UTC)
    t3 = datetime(2026, 5, 24, 10, 10, 0, tzinfo=UTC)

    with freeze_time(t1):
        fake_stream.fire_frame(
            MOCK_VEHICLE_ID, Telemetry(voltage=build_metric_value(400.0))
        )
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t1

    with freeze_time(t2):
        # This batch carries soc only, so the voltage slot stays untouched.
        fake_stream.fire_frame(MOCK_VEHICLE_ID, Telemetry(soc=build_metric_value(50.0)))
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t1

    with freeze_time(t3):
        fake_stream.fire_frame(
            MOCK_VEHICLE_ID, Telemetry(voltage=build_metric_value(410.0))
        )
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t3


# Symmetric reject: malformed provider input is rejected on live AND restore.


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_provider_attribute_appears_from_live_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """A live frame carrying a provider exposes ``state.attributes["provider"]``."""

    await _restart_setup(hass, config_entry_with_vehicles)

    _fire_voltage(
        config_entry_with_vehicles, fake_stream, 400.0, provider=RESTORED_PROVIDER
    )
    await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("provider") == RESTORED_PROVIDER


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_provider_attribute_absent_when_live_frame_lacks_provider(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """No prior + frame without a provider → ``provider`` key absent."""

    await _restart_setup(hass, config_entry_with_vehicles)

    _fire_voltage(config_entry_with_vehicles, fake_stream, 400.0, provider=None)
    await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert "provider" not in state.attributes


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_provider_attribute_restored_from_recorder_when_no_live_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """Restored ``provider`` surfaces even before any live frame arrives."""

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
        restored_states=[
            _voltage_restored_state(provider=RESTORED_PROVIDER),
        ],
    )

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("provider") == RESTORED_PROVIDER
    stamp = state.attributes.get("last_reported_at")
    assert isinstance(stamp, datetime)
    assert stamp == RESTORED_STAMP_DT


@pytest.mark.usefixtures("mock_abrp_client")
async def test_provider_per_attribute_live_wins_over_restored(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """Live and restored attributes compose per-attribute, not whole-mapping."""

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
        restored_states=[
            _voltage_restored_state(provider=RESTORED_PROVIDER),
        ],
    )

    t2 = datetime(2026, 5, 24, 14, 0, 0, tzinfo=UTC)
    with freeze_time(t2):
        _fire_voltage(config_entry_with_vehicles, fake_stream, 420.0, provider=None)
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("provider") == RESTORED_PROVIDER
    assert state.attributes.get("last_reported_at") == t2
    # Value axis: a regression decoupling value from attribute publishing
    # would slip past the attribute-only assertions above.
    assert float(state.state) == 420.0


@pytest.mark.parametrize(
    "restored_provider",
    [
        pytest.param("", id="restored_empty_string"),
        pytest.param(123, id="restored_int"),
        pytest.param(True, id="restored_bool"),
        pytest.param({"nested": "dict"}, id="restored_dict"),
        pytest.param([1, 2, 3], id="restored_list"),
        pytest.param(None, id="restored_none"),
        # Whitespace is non-canonical wire shape, so padding is rejected too.
        pytest.param("   ", id="restored_whitespace_only_spaces"),
        pytest.param("\t\n", id="restored_whitespace_only_tabs_newlines"),
        pytest.param(
            "  RIVIAN_STREAM  ",
            id="restored_leading_trailing_whitespace",
        ),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_provider_attribute_absent_when_restored_value_malformed(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    restored_provider: Any,
) -> None:
    """Malformed restored ``provider`` → attribute OMITTED entirely on the entity."""

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
        restored_states=[_voltage_restored_state(provider=restored_provider)],
    )

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert "provider" not in state.attributes
    # A malformed provider must not collapse the whole attribute dict.
    stamp = state.attributes.get("last_reported_at")
    assert isinstance(stamp, datetime)
    assert stamp == RESTORED_STAMP_DT


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_vehicle_absent_from_garage_skips_eager_create_with_restore_cache(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """Registry + recorder hold a voltage row but the garage is empty → skip."""
    # The vehicle was removed from the ABRP garage since the last run.
    mock_abrp_client.return_value = []
    entry = config_entry_with_vehicles

    await _restart_setup(
        hass,
        entry,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
        restored_states=[_voltage_restored_state()],
    )

    assert hass.states.get(VOLTAGE_ENTITY_ID) is None


@pytest.mark.parametrize(
    "bad_native_value",
    [
        pytest.param("not-a-number", id="non_numeric_string"),
        pytest.param(True, id="bool_true"),
        pytest.param(False, id="bool_false"),
        pytest.param({"nested": "dict"}, id="dict"),
        pytest.param([1, 2], id="list"),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_restored_native_value_rejected_when_malformed(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    bad_native_value: Any,
) -> None:
    """Malformed restored ``native_value`` + no live frame → entity unavailable."""

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
        restored_states=[_voltage_restored_state(native_value=bad_native_value)],
    )

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.state == "unavailable"


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_foreign_config_entry_voltage_row_skipped_by_eager_probe(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    token_entry: dict[str, Any],
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """Eager-create probe filters on ``config_entry_id``, skipping foreign rows."""

    # Same OIDC sub so unique_id collides, but a different entry_id.
    foreign_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        entry_id="01FOREIGNENTRYIDXXXXXXXXXX",
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
        },
    )
    foreign_entry.add_to_hass(hass)
    # Uses the same unique_id formula the entry under test would compute.
    foreign_row = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id=f"{SENSOR_TEST_SUB}_{MOCK_VEHICLE_ID}_voltage",
        config_entry=foreign_entry,
        suggested_object_id="rivian_r2_2027_standard_long_range_voltage",
    )

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        # No preseed: the foreign row is the only entry for this unique_id.
    )

    # The entry under test must not re-claim the row via the eager probe.
    refetched = entity_registry.async_get(foreign_row.entity_id)
    assert refetched is not None
    assert refetched.config_entry_id == foreign_entry.entry_id


@pytest.mark.parametrize(
    "preseed_registry_keys",
    [
        pytest.param(["voltage"], id="one_metric"),
        pytest.param(["voltage", "soc"], id="several_metrics"),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_repeated_garage_vehicle_restores_one_entity_per_metric(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    preseed_registry_keys: list[str],
) -> None:
    """A garage repeating a vehicle must not rebuild its restored sensors twice."""
    mock_abrp_client.return_value = [
        AbrpVehicle(
            vehicle_id=MOCK_VEHICLE_ID,
            name=MOCK_VEHICLE_NAME,
            vehicle_model=MOCK_VEHICLE_MODEL,
            paint=MOCK_PAINT,
        )
    ] * 2

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=preseed_registry_keys,
    )

    assert "does not generate unique IDs" not in caplog.text
    assert len(hass.states.async_entity_ids("sensor")) == len(preseed_registry_keys)


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_staleness_survives_restart_after_terminal_auth_failure(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A value stored while unavailable keeps the stamp that says how old it is.

    A terminal auth failure marks entities unavailable, and Home Assistant
    writes no attributes for an unavailable entity. Persisting the stamp as
    extra data instead is what stops the restored value coming back with no
    indication of its age.
    """
    unavailable_state = State(VOLTAGE_ENTITY_ID, STATE_UNAVAILABLE)
    extra_data: dict[str, Any] = {
        "native_value": RESTORED_VOLTAGE,
        "native_unit_of_measurement": "V",
        "last_reported_at": RESTORED_STAMP_ISO,
        "provider": RESTORED_PROVIDER,
    }

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
        restored_states=[(unavailable_state, extra_data)],
    )

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.state == str(RESTORED_VOLTAGE)
    assert state.attributes.get("last_reported_at") == RESTORED_STAMP_DT
    assert state.attributes.get("provider") == RESTORED_PROVIDER
