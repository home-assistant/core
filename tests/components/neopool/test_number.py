"""Tests for the NeoPool number platform."""

import asyncio
from datetime import timedelta
import gc
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from neopool_modbus.exceptions import NeoPoolConnectionError
from neopool_modbus.registers import MaskedFlag, SetpointKind
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, PERCENTAGE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform, entity_registry as er

from . import setup_integration
from .conftest import MOCK_POOL_DATA

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

# Longer than the entity's settle delay so a single tick flushes the write.
FLUSH = timedelta(seconds=5)
# Shorter than the settle delay: advancing by this must NOT flush a pending write.
PARTIAL = timedelta(seconds=2)


def _number_entity_id(
    hass: HomeAssistant, entry: MockConfigEntry, key_lower_suffix: str
) -> str:
    registry = er.async_get(hass)
    entries = [
        e
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.domain == NUMBER_DOMAIN and e.unique_id.endswith(f"_{key_lower_suffix}")
    ]
    assert entries, (
        f"no number entity ending in _{key_lower_suffix}, found: "
        + ", ".join(
            e.unique_id
            for e in er.async_entries_for_config_entry(registry, entry.entry_id)
            if e.domain == NUMBER_DOMAIN
        )
    )
    return entries[0].entity_id


async def _set_value(hass: HomeAssistant, entity_id: str, value: float) -> None:
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {"entity_id": entity_id, ATTR_VALUE: value},
        blocking=True,
    )


def _set_value_nowait(
    hass: HomeAssistant, entity_id: str, value: float
) -> asyncio.Task[None]:
    """Start a blocking set_value as a task so the freezer can drive the flush.

    A blocking call now awaits the debounced write, which only runs on a
    freezer tick. Awaiting it inline would deadlock, so callers schedule it,
    flush, then await the task to observe the write's outcome.
    """
    return hass.async_create_task(_set_value(hass, entity_id, value))


async def _let_park(hass: HomeAssistant) -> None:
    """Yield enough for a scheduled set_value task to reach its await point.

    ``async_block_till_done`` waits on hass-tracked tasks, so it would block on
    a set_value task intentionally parked before the flush; plain event-loop
    yields let the task register its optimistic state without that wait.
    """
    for _ in range(3):
        await asyncio.sleep(0)


async def _write(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
    value: float,
) -> None:
    """Set a value, flush the debounce, and await the write's outcome.

    Raises whatever the debounced write raises (a device error surfaces to the
    blocking caller), matching how a ``blocking: true`` service call behaves.
    """
    task = _set_value_nowait(hass, entity_id, value)
    await _flush(hass, freezer)
    await task


async def _flush(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance past the debounce cooldown and let the pending write run."""
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance by less than the cooldown; a pending write must not fire yet.

    Uses event-loop yields rather than ``async_block_till_done`` so a set_value
    task parked on the coalesce future does not stall the advance.
    """
    freezer.tick(PARTIAL)
    async_fire_time_changed(hass)
    await _let_park(hass)


async def _poll(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MagicMock,
    data: dict[str, Any],
) -> None:
    """Push a coordinator poll returning ``data``."""
    mock_client.async_read_all.return_value = data
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_simple_number_writes_register_after_debounce(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Setting a numeric value dispatches to the correct high-level API."""
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )

    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    mock_neopool_client.async_set_setpoint.reset_mock()

    await _write(hass, freezer, ph1_entity_id, 7.5)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.PH_MAX, 750
    )

    smart_entity_id = _number_entity_id(
        hass, mock_config_entry_number, "mbf_par_smart_temp_high"
    )
    mock_neopool_client.async_set_setpoint.reset_mock()

    await _write(hass, freezer, smart_entity_id, 30.0)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.SMART_TEMP_HIGH, 30
    )


async def test_scaled_setpoint_optimistic_value_is_ui_scaled(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Optimistic state after a scaled setpoint write is UI-scaled.

    The lib override carries the raw register value (7.5 pH -> 750), but the
    entity state must read back the decoded value. Regression guard: the merged
    optimistic value must surface as 7.5, not 750.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )

    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    await _write(hass, freezer, ph1_entity_id, 7.5)

    state = hass.states.get(ph1_entity_id)
    assert state is not None
    assert float(state.state) == 7.5


async def test_pending_value_shown_optimistically_before_write(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """State surfaces the requested value while the debounce is in flight.

    Until the debounced write merges the override, the coordinator still holds
    the old register. The entity must report the requested value optimistically
    so the UI does not snap back to the stale reading before the cooldown fires.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")

    task = _set_value_nowait(hass, ph1_entity_id, 7.5)
    # Advance less than the cooldown: the optimistic state is set, no write yet.
    await _advance(hass, freezer)

    state = hass.states.get(ph1_entity_id)
    assert state is not None
    assert float(state.state) == 7.5
    mock_neopool_client.async_set_setpoint.assert_not_awaited()

    # Let the queued write settle so the awaiting task finishes cleanly.
    await _flush(hass, freezer)
    await task


async def test_scaled_write_rounds_to_nearest_register_int(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The scaled register value is rounded, not truncated.

    Regression guard: ``4.1 * 100`` evaluates to ``409.999...`` in float, so a
    plain ``int()`` would write 409. The write must round to 410.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 410}
    )
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    mock_neopool_client.async_set_setpoint.reset_mock()

    await _write(hass, freezer, ph1_entity_id, 4.1)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.PH_MAX, 410
    )


async def test_heating_setpoint_writes_via_high_level_api(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Writing the heating setpoint delegates to async_set_setpoint(HEATING)."""
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_HEATING_TEMP": 28}
    )

    await setup_integration(hass, mock_config_entry_number)
    entity_id = _number_entity_id(
        hass, mock_config_entry_number, "mbf_par_heating_temp"
    )
    mock_neopool_client.async_set_setpoint.reset_mock()

    await _write(hass, freezer, entity_id, 28.0)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.HEATING, 28
    )


@pytest.mark.parametrize(
    ("suffix", "data_key", "value", "kind", "expected_raw"),
    [
        pytest.param("mbf_par_ph1", "MBF_PAR_PH1", 7.2, SetpointKind.PH_MAX, 720),
        pytest.param("mbf_par_ph2", "MBF_PAR_PH2", 7.0, SetpointKind.PH_MIN, 700),
        pytest.param("mbf_par_rx1", "MBF_PAR_RX1", 700, SetpointKind.REDOX, 700),
        pytest.param("mbf_par_cl1", "MBF_PAR_CL1", 1.5, SetpointKind.CHLORINE, 150),
        pytest.param("mbf_par_hidro", "MBF_PAR_HIDRO", 50, SetpointKind.HIDRO, 500),
        pytest.param(
            "mbf_par_smart_temp_high",
            "MBF_PAR_SMART_TEMP_HIGH",
            18,
            SetpointKind.SMART_TEMP_HIGH,
            18,
        ),
        pytest.param(
            "mbf_par_smart_temp_low",
            "MBF_PAR_SMART_TEMP_LOW",
            12,
            SetpointKind.SMART_TEMP_LOW,
            12,
        ),
    ],
)
async def test_setpoint_write_targets_map_to_kind_and_scale(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    suffix: str,
    data_key: str,
    value: float,
    kind: SetpointKind,
    expected_raw: int,
) -> None:
    """Each setpoint entity writes to its own SetpointKind with the right scale.

    A wrong enum or scale in a single description would pass the snapshots and
    the generic debounce tests, so exercise every write target explicitly.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={data_key: expected_raw}
    )
    await setup_integration(hass, mock_config_entry_number)

    entity_id = _number_entity_id(hass, mock_config_entry_number, suffix)
    mock_neopool_client.async_set_setpoint.reset_mock()

    await _write(hass, freezer, entity_id, value)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(kind, expected_raw)


async def test_number_state_returns_raw_register_value(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The entity state reflects the register value the coordinator holds."""
    await setup_integration(hass, mock_config_entry_number)
    await _poll(
        hass, freezer, mock_neopool_client, {**MOCK_POOL_DATA, "MBF_PAR_PH1": 7.55}
    )

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    state = hass.states.get(ph1_entity_id)
    assert state is not None
    assert float(state.state) == 7.55


@pytest.mark.parametrize(
    ("visual_style", "expected_unit", "expected_step", "expected_max"),
    [
        pytest.param(0x4000, PERCENTAGE, "1.0", 100, id="percent"),
        pytest.param(0x2000, "g/h", "0.1", 85, id="grh"),
    ],
)
async def test_hidro_units_follow_visual_style(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    visual_style: int,
    expected_unit: str,
    expected_step: str,
    expected_max: int,
) -> None:
    """MBF_PAR_HIDRO unit, step and max follow the reported percent/g-h mode.

    MBF_PAR_UICFG_MACH_VISUAL_STYLE forces percentage (0x4000) or g/h (0x2000).
    Percent mode caps at 100; g/h mode uses the reported nominal
    (MBF_PAR_HIDRO_NOM). The nominal is a non-100 value so percent fails if the
    maximum falls back to reading it.
    """
    await setup_integration(hass, mock_config_entry_number)
    await _poll(
        hass,
        freezer,
        mock_neopool_client,
        {
            **MOCK_POOL_DATA,
            "MBF_PAR_HIDRO_NOM": 85,
            "MBF_PAR_MODEL": 0x0002,
            "MBF_PAR_UICFG_MACH_VISUAL_STYLE": visual_style,
        },
    )

    entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_hidro")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == expected_unit
    assert state.attributes["step"] == float(expected_step)
    assert state.attributes["max"] == expected_max


async def test_masked_number_state_decodes_field(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Masked compound numbers decode their field from the shared register.

    HIDRO_COVER_REDUCTION / SHUTDOWN_TEMPERATURE share register 0x042D: the
    lower byte holds cover reduction %, the upper byte the shutdown temperature.
    Each entity's state must isolate its own field.
    """
    await setup_integration(hass, mock_config_entry_number)
    await _poll(
        hass,
        freezer,
        mock_neopool_client,
        {**MOCK_POOL_DATA, "MBF_PAR_HIDRO_COVER_REDUCTION": 0x0C19},
    )

    cover_id = _number_entity_id(
        hass, mock_config_entry_number, "mbf_par_hidro_cover_reduction"
    )
    shutdown_id = _number_entity_id(
        hass, mock_config_entry_number, "mbf_par_hidro_shutdown_temperature"
    )
    cover = hass.states.get(cover_id)
    shutdown = hass.states.get(shutdown_id)
    assert cover is not None and float(cover.state) == 25
    assert shutdown is not None and float(shutdown.state) == 12


@pytest.mark.parametrize(
    ("key_suffix", "flag", "value", "register_result"),
    [
        (
            "mbf_par_hidro_cover_reduction",
            MaskedFlag.HIDRO_COVER_REDUCTION_PERCENT,
            50,
            0x0C32,  # shutdown temp 12 (0x0C) in the high byte, cover 50 (0x32)
        ),
        (
            "mbf_par_hidro_shutdown_temperature",
            MaskedFlag.HIDRO_SHUTDOWN_TEMPERATURE,
            15,
            0x0F19,  # shutdown temp 15 (0x0F) in the high byte, cover 25 (0x19)
        ),
    ],
)
async def test_masked_number_write_passes_field_value(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    key_suffix: str,
    flag: MaskedFlag,
    value: float,
    register_result: int,
) -> None:
    """Writing one masked number dispatches to async_set_masked_register.

    The read-modify-write that keeps the sibling byte intact is a lib concern
    (``async_set_masked_register`` performs it internally). Each entity passes
    its own *field value*, not the packed 16-bit register, tagged with its own
    masked flag: the two share register 0x042D but map to distinct fields.
    """
    mock_neopool_client.async_set_masked_register = AsyncMock(
        return_value={"MBF_PAR_HIDRO_COVER_REDUCTION": register_result}
    )

    await setup_integration(hass, mock_config_entry_number)
    await _poll(
        hass,
        freezer,
        mock_neopool_client,
        {**MOCK_POOL_DATA, "MBF_PAR_HIDRO_COVER_REDUCTION": 0x0C19},
    )

    entity_id = _number_entity_id(hass, mock_config_entry_number, key_suffix)
    mock_neopool_client.async_set_masked_register.reset_mock()

    await _write(hass, freezer, entity_id, value)

    mock_neopool_client.async_set_masked_register.assert_awaited_once_with(flag, value)
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == value


async def test_write_works_after_entity_id_change(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A write still reaches the device after the entity is renamed.

    Changing the entity ID removes and re-adds the same object. If removal
    leaves the removing flag set, every later flush aborts and the write never
    reaches the device, so the write must run against the new entity ID.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    new_entity_id = f"{ph1_entity_id}_renamed"
    entity_registry.async_update_entity(ph1_entity_id, new_entity_id=new_entity_id)
    await hass.async_block_till_done()
    assert hass.states.get(new_entity_id) is not None

    mock_neopool_client.async_set_setpoint.reset_mock()
    await _write(hass, freezer, new_entity_id, 7.5)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.PH_MAX, 750
    )
    state = hass.states.get(new_entity_id)
    assert state is not None
    assert float(state.state) == 7.5


async def test_masked_writes_are_serialized(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Concurrent masked writes serialize through the coordinator lock.

    Cover reduction and shutdown temperature share one packed register, so
    their read-modify-write must not overlap; otherwise the later write would
    restore the sibling byte to a stale value.
    """
    overlap = False
    active = 0

    async def _slow_masked(flag: MaskedFlag, value: int) -> dict[str, Any]:
        nonlocal overlap, active
        active += 1
        if active > 1:
            overlap = True
        await asyncio.sleep(0)
        active -= 1
        return {"MBF_PAR_HIDRO_COVER_REDUCTION": 0x0C19}

    mock_neopool_client.async_set_masked_register = AsyncMock(side_effect=_slow_masked)

    await setup_integration(hass, mock_config_entry_number)
    await _poll(
        hass,
        freezer,
        mock_neopool_client,
        {**MOCK_POOL_DATA, "MBF_PAR_HIDRO_COVER_REDUCTION": 0x0C19},
    )

    cover_id = _number_entity_id(
        hass, mock_config_entry_number, "mbf_par_hidro_cover_reduction"
    )
    shutdown_id = _number_entity_id(
        hass, mock_config_entry_number, "mbf_par_hidro_shutdown_temperature"
    )

    # Queue both writes so their debounced flushes race the shared register.
    cover_task = _set_value_nowait(hass, cover_id, 50)
    shutdown_task = _set_value_nowait(hass, shutdown_id, 20)
    await _flush(hass, freezer)
    await asyncio.gather(cover_task, shutdown_task)

    assert not overlap
    assert mock_neopool_client.async_set_masked_register.await_count == 2


@pytest.mark.parametrize(
    "write_error",
    [
        pytest.param(NeoPoolConnectionError("boom"), id="lib-connection-error"),
        pytest.param(TimeoutError("boom"), id="timeout"),
        pytest.param(OSError("boom"), id="os-error"),
    ],
)
async def test_number_write_raises_communication_error(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    write_error: Exception,
) -> None:
    """A device error in the debounced write surfaces to the blocking caller.

    The write is coalesced behind a shared future the blocking service call
    awaits, so a communication failure raises HomeAssistantError (matching the
    switch platform) instead of being swallowed.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(side_effect=write_error)
    await setup_integration(hass, mock_config_entry_number)
    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")

    task = _set_value_nowait(hass, ph1_entity_id, 7.5)
    await _flush(hass, freezer)
    with pytest.raises(HomeAssistantError) as err:
        await task

    assert err.value.translation_key == "modbus_communication_error"
    mock_neopool_client.async_set_setpoint.assert_awaited_once()


async def test_optimistic_state_rolls_back_on_write_failure(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed write rolls the optimistic state back to the device reading.

    The requested value shows optimistically while the write is queued; when the
    device rejects it, the state must snap back to the last known register value
    rather than linger on the value that never took.
    """
    await setup_integration(hass, mock_config_entry_number)
    await _poll(
        hass, freezer, mock_neopool_client, {**MOCK_POOL_DATA, "MBF_PAR_PH1": 7.0}
    )

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    mock_neopool_client.async_set_setpoint = AsyncMock(
        side_effect=NeoPoolConnectionError("boom")
    )

    task = _set_value_nowait(hass, ph1_entity_id, 7.5)
    await _let_park(hass)

    # Optimistic value is shown while the write is in flight.
    state = hass.states.get(ph1_entity_id)
    assert state is not None
    assert float(state.state) == 7.5

    await _flush(hass, freezer)
    with pytest.raises(HomeAssistantError):
        await task

    state = hass.states.get(ph1_entity_id)
    assert state is not None
    assert float(state.state) == 7.0


async def test_coalesced_callers_all_succeed_together(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Three quick set_value calls collapse to one write and all callers succeed.

    Every caller awaits the same coalesce future, so the single write of the
    last value resolves them together.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    mock_neopool_client.async_set_setpoint.reset_mock()

    tasks = [_set_value_nowait(hass, ph1_entity_id, value) for value in (7.0, 7.2, 7.5)]
    await _flush(hass, freezer)
    results = await asyncio.gather(*tasks)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.PH_MAX, 750
    )
    assert results == [None, None, None]


async def test_coalesced_callers_all_raise_together(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed coalesced write raises for every caller in the debounce window.

    All three blocking callers await the shared future, so the single write's
    device error surfaces to each of them.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        side_effect=NeoPoolConnectionError("boom")
    )
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    mock_neopool_client.async_set_setpoint.reset_mock()

    tasks = [_set_value_nowait(hass, ph1_entity_id, value) for value in (7.0, 7.2, 7.5)]
    await _flush(hass, freezer)
    results = await asyncio.gather(*tasks, return_exceptions=True)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.PH_MAX, 750
    )
    assert all(isinstance(r, HomeAssistantError) for r in results)


async def test_failed_write_survives_a_cancelled_coalesced_caller(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed coalesced write raises for the survivor and logs no warning.

    Two callers share one coalesce future; one is cancelled before the delayed
    write fails. Cancelling a caller makes asyncio.shield attach its own logger
    to the shared future, so failing it via set_exception would be reported as
    an unretrieved error at teardown. The write instead carries its outcome as
    the future's result, so the survivor still re-raises the device error and
    no "exception in shielded future" warning is logged.
    """
    in_write = asyncio.Event()
    release = asyncio.Event()

    async def _blocking_boom(kind: SetpointKind, value: int) -> dict[str, Any]:
        in_write.set()
        await release.wait()
        raise NeoPoolConnectionError("boom")

    mock_neopool_client.async_set_setpoint = AsyncMock(side_effect=_blocking_boom)
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")

    # Two callers coalesce onto one batch; the write enters the library call and
    # blocks there, so both are parked on the shared shielded future.
    victim = _set_value_nowait(hass, ph1_entity_id, 7.5)
    survivor = _set_value_nowait(hass, ph1_entity_id, 7.5)
    await _let_park(hass)
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await in_write.wait()

    # Cancel one caller; the shield spares the batch, so the write still runs.
    victim.cancel()
    with pytest.raises(asyncio.CancelledError):
        await victim

    # Let the shielded write finish and fail; the survivor observes the error.
    release.set()
    with pytest.raises(HomeAssistantError):
        await survivor
    await hass.async_block_till_done()

    # Force a GC pass so any unretrieved shielded future would surface a warning.
    gc.collect()
    await asyncio.sleep(0)

    assert "exception in shielded future" not in caplog.text
    assert "exception was never retrieved" not in caplog.text


async def test_write_queued_during_flush_gets_its_own_outcome(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A set_value arriving mid-flush writes on its own, not the in-flight batch.

    While the first flush is awaiting device I/O, a new set_value must not reuse
    the in-flight future: it would return the first write's outcome and its own
    value would never reach the device. Each batch gets its own future and its
    own serialized write.
    """
    in_write = asyncio.Event()
    release = asyncio.Event()
    seen: list[int] = []

    async def _gated_setpoint(kind: SetpointKind, value: int) -> dict[str, Any]:
        seen.append(value)
        if len(seen) == 1:
            in_write.set()
            await release.wait()
        return {"MBF_PAR_PH1": value}

    mock_neopool_client.async_set_setpoint = AsyncMock(side_effect=_gated_setpoint)
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    mock_neopool_client.async_set_setpoint.reset_mock()
    seen.clear()

    # First write enters the library call and blocks there.
    first = _set_value_nowait(hass, ph1_entity_id, 7.0)
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await in_write.wait()

    # A second value arrives while the first write is still in flight.
    second = _set_value_nowait(hass, ph1_entity_id, 8.0)
    await _let_park(hass)

    # Release the first write, then flush the second batch.
    release.set()
    await first
    await _flush(hass, freezer)
    await second

    # Two distinct writes ran, each with its own value.
    assert seen == [700, 800]
    state = hass.states.get(ph1_entity_id)
    assert state is not None
    assert float(state.state) == 8.0


async def test_same_value_queued_during_flush_still_resolves(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A second set_value of the same value mid-flush still gets an outcome.

    The two batches carry the same float value, so telling them apart by value
    alone fails: the first flush would clear the second batch's pending value,
    its own flush would then find nothing queued, and the newer caller would be
    left cancelled. Each batch is tagged, so the newer caller resolves.
    """
    in_write = asyncio.Event()
    release = asyncio.Event()
    seen: list[int] = []

    async def _gated_setpoint(kind: SetpointKind, value: int) -> dict[str, Any]:
        seen.append(value)
        if len(seen) == 1:
            in_write.set()
            await release.wait()
        return {"MBF_PAR_PH1": value}

    mock_neopool_client.async_set_setpoint = AsyncMock(side_effect=_gated_setpoint)
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    mock_neopool_client.async_set_setpoint.reset_mock()
    seen.clear()

    # First write enters the library call and blocks there.
    first = _set_value_nowait(hass, ph1_entity_id, 7.0)
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await in_write.wait()

    # The same value arrives again while the first write is still in flight.
    second = _set_value_nowait(hass, ph1_entity_id, 7.0)
    await _let_park(hass)

    # Release the first write, then flush the second batch. Both callers must
    # observe an outcome; neither is left cancelled.
    release.set()
    await first
    await _flush(hass, freezer)
    await second

    # Both same-valued batches reached the client as distinct writes.
    assert seen == [700, 700]
    state = hass.states.get(ph1_entity_id)
    assert state is not None
    assert float(state.state) == 7.0


async def test_unexpected_write_error_reaches_caller(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An unexpected write error still fails the blocking caller.

    A raise outside the device-error set must not resolve the coalesce future as
    a success: the caller would otherwise see a successful service call while the
    value never reached the device. It surfaces unchanged, not relabeled as a
    communication error.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(side_effect=ValueError("boom"))
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")

    task = _set_value_nowait(hass, ph1_entity_id, 7.5)
    await _flush(hass, freezer)
    with pytest.raises(ValueError, match="boom"):
        await task


async def test_post_write_merge_failure_reaches_caller(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A raise after a successful device write still fails the caller.

    The device write succeeds, but merging the result into the coordinator
    raises. The flush must not fall through to a success result: the failure
    surfaces unchanged, not relabeled as a communication error, since the write
    itself succeeded.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    mock_neopool_client.async_set_setpoint.reset_mock()

    task = _set_value_nowait(hass, ph1_entity_id, 7.5)
    with patch.object(
        mock_config_entry_number.runtime_data,
        "async_set_updated_data",
        side_effect=RuntimeError("merge boom"),
    ):
        await _flush(hass, freezer)
        with pytest.raises(RuntimeError, match="merge boom"):
            await task


async def test_optimistic_value_survives_overlapping_flush(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A newer optimistic value is not clobbered by an in-flight older write.

    The first flush holds the write lock while its device call blocks. A second
    debounce elapses and queues a newer value. When the first write commits, it
    must keep showing the newer optimistic value, not republish its own older
    value for the duration of the second write.
    """
    release = asyncio.Event()
    in_write = asyncio.Event()
    seen: list[int] = []

    async def _gated_setpoint(kind: SetpointKind, value: int) -> dict[str, Any]:
        seen.append(value)
        if len(seen) == 1:
            in_write.set()
            await release.wait()
        return {"MBF_PAR_PH1": value}

    mock_neopool_client.async_set_setpoint = AsyncMock(side_effect=_gated_setpoint)
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    mock_neopool_client.async_set_setpoint.reset_mock()
    seen.clear()

    # First write enters the library call and blocks there.
    first = _set_value_nowait(hass, ph1_entity_id, 7.0)
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await in_write.wait()

    # A newer value arrives while the first write is still in flight.
    second = _set_value_nowait(hass, ph1_entity_id, 8.0)
    await _let_park(hass)

    # Release the first write; it commits its older value to the coordinator but
    # must keep showing the newer optimistic value rather than republishing 7.0.
    release.set()
    await first
    state = hass.states.get(ph1_entity_id)
    assert state is not None
    assert float(state.state) == 8.0

    # The second write then runs and confirms the newer value on the device.
    await _flush(hass, freezer)
    await second
    assert seen == [700, 800]
    state = hass.states.get(ph1_entity_id)
    assert state is not None
    assert float(state.state) == 8.0


async def test_repeated_set_value_writes_only_latest(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Two quick set_value calls debounce to a single write of the last value."""
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    mock_neopool_client.async_set_setpoint.reset_mock()

    task1 = _set_value_nowait(hass, ph1_entity_id, 7.0)
    task2 = _set_value_nowait(hass, ph1_entity_id, 7.5)
    await _flush(hass, freezer)
    await asyncio.gather(task1, task2)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.PH_MAX, 750
    )


async def test_stepper_settle_restarts_timer(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Each click restarts the timer; the write fires after the last click.

    Two clicks 2s apart (each under the 3s settle delay) span 4s in total. A
    fixed-window debounce anchored to the first click would have written the
    intermediate value at 3s; the restart-on-click behavior must instead write
    only the final value once the stepper settles.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    mock_neopool_client.async_set_setpoint.reset_mock()

    task1 = _set_value_nowait(hass, ph1_entity_id, 7.0)
    await _advance(hass, freezer)
    task2 = _set_value_nowait(hass, ph1_entity_id, 7.5)
    await _advance(hass, freezer)

    # 4s elapsed since the first click, but only 2s since the last: no write yet.
    mock_neopool_client.async_set_setpoint.assert_not_awaited()

    await _flush(hass, freezer)
    await asyncio.gather(task1, task2)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.PH_MAX, 750
    )


async def test_no_write_when_settled_value_unchanged(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A sweep that lands back on the current value writes nothing.

    Stepping away and back to the device's value must not burn an EEPROM cycle:
    the settled raw value equals the coordinator's, so the write is skipped.
    An off-step request that rounds to the same register must also drop the
    optimistic state back to the device reading instead of lingering.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )
    await setup_integration(hass, mock_config_entry_number)
    await _poll(
        hass, freezer, mock_neopool_client, {**MOCK_POOL_DATA, "MBF_PAR_PH1": 7.5}
    )

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    mock_neopool_client.async_set_setpoint.reset_mock()

    task1 = _set_value_nowait(hass, ph1_entity_id, 8.0)
    task2 = _set_value_nowait(hass, ph1_entity_id, 7.5)
    await _flush(hass, freezer)
    await asyncio.gather(task1, task2)

    mock_neopool_client.async_set_setpoint.assert_not_awaited()
    state = hass.states.get(ph1_entity_id)
    assert state is not None
    assert float(state.state) == 7.5

    # Off-step request rounding to the same register: no write, and the UI must
    # snap back from the optimistic 7.504 to the device value.
    await _write(hass, freezer, ph1_entity_id, 7.504)

    mock_neopool_client.async_set_setpoint.assert_not_awaited()
    state = hass.states.get(ph1_entity_id)
    assert state is not None
    assert float(state.state) == 7.5


async def test_pending_write_dropped_on_remove(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unloading cancels an un-elapsed write and releases the awaiting caller.

    The queued write must never fire, and the blocking caller awaiting the
    coalesce future exits cleanly (cancellation, not an error) when the entity
    is removed mid-wait.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    task = _set_value_nowait(hass, ph1_entity_id, 7.5)
    await _let_park(hass)

    # Unload before the cooldown elapses: the queued write must never fire.
    await hass.config_entries.async_unload(mock_config_entry_number.entry_id)
    await _flush(hass, freezer)

    # The awaiting caller returns without raising once the future is cancelled.
    await task
    mock_neopool_client.async_set_setpoint.assert_not_awaited()


async def test_external_cancel_propagates_but_spares_coalesced_caller(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Cancelling one caller re-raises for it but spares the coalesced batch.

    Two blocking callers land in the same debounce window and share one
    coalesce future. Cancelling one caller's service task must propagate the
    cancellation to that caller alone: the shield keeps the shared future
    alive, so the write still fires and the surviving caller observes its
    outcome without a spurious cancellation.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    mock_neopool_client.async_set_setpoint.reset_mock()

    victim = _set_value_nowait(hass, ph1_entity_id, 7.5)
    survivor = _set_value_nowait(hass, ph1_entity_id, 7.5)
    await _let_park(hass)

    # Cancel only the victim's task; its cancellation must propagate to it.
    victim.cancel()
    with pytest.raises(asyncio.CancelledError):
        await victim

    # The batch is untouched: the queued write fires and the survivor, still
    # awaiting the shielded future, returns cleanly with the write's outcome.
    await _flush(hass, freezer)
    await survivor
    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.PH_MAX, 750
    )


async def test_inflight_write_skips_coordinator_on_remove(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A write already in flight when the entity is removed skips the coordinator.

    The scheduled call can only be cancelled before it fires. Once the write is
    inside a library call and the entity is removed, it must not merge into or
    refresh the coordinator whose client is being torn down.
    """
    in_write = asyncio.Event()
    release = asyncio.Event()

    async def _blocking_setpoint(kind: SetpointKind, value: int) -> dict[str, Any]:
        in_write.set()
        await release.wait()
        return {"MBF_PAR_PH1": value}

    mock_neopool_client.async_set_setpoint = AsyncMock(side_effect=_blocking_setpoint)
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    task = _set_value_nowait(hass, ph1_entity_id, 7.5)
    await _let_park(hass)

    # Let the timer fire and the write enter the library call, then block there.
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await in_write.wait()

    with patch.object(
        mock_config_entry_number.runtime_data, "async_set_updated_data"
    ) as mock_update:
        await hass.config_entries.async_unload(mock_config_entry_number.entry_id)
        release.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    await task
    mock_neopool_client.async_set_setpoint.assert_awaited_once()
    mock_update.assert_not_called()


async def test_client_close_waits_for_inflight_flush(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The client close waits for an in-flight flush, so no write outlives it.

    Removal cancels the flush task and awaits it before ``async_unload_entry``
    closes the client, so the device call has unwound by the time the client
    goes away. A close reaching a live connection while the write is still in
    the library call would race the teardown.
    """
    in_write = asyncio.Event()
    write_active = False
    close_saw_write_active: bool | None = None

    async def _blocking_setpoint(kind: SetpointKind, value: int) -> dict[str, Any]:
        nonlocal write_active
        write_active = True
        in_write.set()
        try:
            # Never released: removal must cancel this to let the unload finish.
            await asyncio.Event().wait()
            return {"MBF_PAR_PH1": value}
        finally:
            write_active = False

    async def _record_close() -> None:
        nonlocal close_saw_write_active
        close_saw_write_active = write_active

    mock_neopool_client.async_set_setpoint = AsyncMock(side_effect=_blocking_setpoint)
    mock_neopool_client.close = AsyncMock(side_effect=_record_close)
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    task = _set_value_nowait(hass, ph1_entity_id, 7.5)
    await _let_park(hass)

    # Let the timer fire and the write enter the library call, then block there.
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await in_write.wait()

    # Unload while the write is in flight. Removal cancels and awaits the flush
    # task, unwinding the setpoint call, so the unload completes without a hang.
    assert await hass.config_entries.async_unload(mock_config_entry_number.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    await task
    mock_neopool_client.close.assert_awaited_once()
    # The in-flight device call had unwound before the client was closed.
    assert close_saw_write_active is False


async def test_client_close_waits_for_all_overlapping_flushes(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Removal cancels every overlapping flush, not just the most recent one.

    Two set_value calls spaced beyond the settle delay start two flush tasks.
    The first is inside the library call (holding the flush lock) when the
    second fires and blocks on that lock. Tracking only the latest task would
    leave the first device call live past removal, racing the client close.
    """
    in_write = asyncio.Event()
    write_active = False
    close_saw_write_active: bool | None = None

    async def _blocking_setpoint(kind: SetpointKind, value: int) -> dict[str, Any]:
        nonlocal write_active
        write_active = True
        in_write.set()
        try:
            # Never released: removal must cancel this to let the unload finish.
            await asyncio.Event().wait()
            return {"MBF_PAR_PH1": value}
        finally:
            write_active = False

    async def _record_close() -> None:
        nonlocal close_saw_write_active
        close_saw_write_active = write_active

    mock_neopool_client.async_set_setpoint = AsyncMock(side_effect=_blocking_setpoint)
    mock_neopool_client.close = AsyncMock(side_effect=_record_close)
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")

    # First write enters the library call and blocks, holding the flush lock.
    first = _set_value_nowait(hass, ph1_entity_id, 7.0)
    await _let_park(hass)
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await in_write.wait()

    # A second value's flush fires while the first is in flight; it blocks on
    # the flush lock as a separate task, so two flush tasks are now active.
    second = _set_value_nowait(hass, ph1_entity_id, 8.0)
    await _let_park(hass)
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await _let_park(hass)

    # Unload must cancel and await both tasks, including the first still in the
    # library call, before the client closes.
    assert await hass.config_entries.async_unload(mock_config_entry_number.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    await first
    await second
    mock_neopool_client.close.assert_awaited_once()
    assert close_saw_write_active is False


def _get_number_entity(hass: HomeAssistant, entity_id: str) -> Any:
    """Return the live NeoPoolNumber object for entity_id."""
    for platform in entity_platform.async_get_platforms(hass, "neopool"):
        if entity_id in platform.entities:
            return platform.entities[entity_id]
    raise AssertionError(f"no number entity {entity_id}")


async def test_flush_aborts_when_removed_while_holding_lock(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A flush that finds the entity removed after winning the lock aborts.

    Removal cancels every tracked flush task, so a queued flush waiting on the
    lock is normally canceled before it can write; the in-lock removal guard
    only fires if a flush wins the lock in the same tick removal flips the flag.
    Drive that directly: hold the flush lock from the test, flip removing, then
    release the lock so the parked flush hits the guard before it touches the
    device.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    entity = _get_number_entity(hass, ph1_entity_id)

    await entity._flush_lock.acquire()
    task = _set_value_nowait(hass, ph1_entity_id, 7.5)
    await _let_park(hass)
    # Fire the debounce timer without async_block_till_done: the flush task
    # parks on the lock we hold, so waiting on it here would deadlock.
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await _let_park(hass)

    # The flush is parked on the lock the test holds. Flip removing, then hand
    # the lock over so the flush enters and aborts at the in-lock guard.
    entity._removing = True
    entity._flush_lock.release()
    await task

    # The guard aborted before any device write.
    mock_neopool_client.async_set_setpoint.assert_not_awaited()
    entity._removing = False


@pytest.mark.usefixtures("mock_neopool_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry_number: MockConfigEntry,
) -> None:
    """Snapshot every entity registered by the number platform."""
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry_number)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_number.entry_id
    )


async def test_setup_when_modules_absent(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    minimal_pool_data: dict[str, Any],
) -> None:
    """No number entities register when no modules are present.

    Every number is gated on a module or relay, so a controller reporting
    none registers nothing. In particular the cover-reduction number must
    not appear without a hydrolysis module.
    """
    mock_neopool_client.async_read_all.return_value = minimal_pool_data
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry_number)
    number_entries = [
        e
        for e in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry_number.entry_id
        )
        if e.domain == NUMBER_DOMAIN
    ]
    assert number_entries == []


@pytest.mark.usefixtures("mock_neopool_client")
async def test_cover_gated_numbers_absent_when_option_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The cover-gated numbers are not created while their option is off.

    Both numbers gate on CONF_USE_COVER_SENSOR, so a config entry without it
    must register neither, even though the hydrolysis module is present.
    """
    await setup_integration(hass, mock_config_entry)
    gated = [
        e
        for e in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if e.domain == NUMBER_DOMAIN
        and e.unique_id.endswith(
            ("_mbf_par_hidro_cover_reduction", "_mbf_par_hidro_shutdown_temperature")
        )
    ]
    assert gated == []
