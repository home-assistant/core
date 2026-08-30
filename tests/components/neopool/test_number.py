"""Tests for the NeoPool number platform."""

import asyncio
from datetime import timedelta
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
from homeassistant.helpers import entity_registry as er

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


async def _flush(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance past the debounce cooldown and let the pending write run."""
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance by less than the cooldown; a pending write must not fire yet."""
    freezer.tick(PARTIAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


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

    await _set_value(hass, ph1_entity_id, 7.5)
    await _flush(hass, freezer)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.PH_MAX, 750
    )

    smart_entity_id = _number_entity_id(
        hass, mock_config_entry_number, "mbf_par_smart_temp_high"
    )
    mock_neopool_client.async_set_setpoint.reset_mock()

    await _set_value(hass, smart_entity_id, 30.0)
    await _flush(hass, freezer)

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
    await _set_value(hass, ph1_entity_id, 7.5)
    await _flush(hass, freezer)

    state = hass.states.get(ph1_entity_id)
    assert state is not None
    assert float(state.state) == 7.5


async def test_pending_value_shown_optimistically_before_write(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
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

    await _set_value(hass, ph1_entity_id, 7.5)

    # No flush: the cooldown has not elapsed, so no write yet.
    state = hass.states.get(ph1_entity_id)
    assert state is not None
    assert float(state.state) == 7.5
    mock_neopool_client.async_set_setpoint.assert_not_awaited()


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

    await _set_value(hass, ph1_entity_id, 4.1)
    await _flush(hass, freezer)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.PH_MAX, 410
    )


async def test_heating_setpoint_writes_via_high_level_api(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Writing the heating setpoint delegates to async_set_setpoint(HEATING).

    Since lib v4 the number entity no longer talks to ``async_set_temp_setpoint``;
    the high-level ``async_set_setpoint`` API owns the write and returns the
    optimistic-update dict the coordinator merges in.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_HEATING_TEMP": 28}
    )

    await setup_integration(hass, mock_config_entry_number)
    entity_id = _number_entity_id(
        hass, mock_config_entry_number, "mbf_par_heating_temp"
    )
    mock_neopool_client.async_set_setpoint.reset_mock()

    await _set_value(hass, entity_id, 28.0)
    await _flush(hass, freezer)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.HEATING, 28
    )


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
    ("visual_style", "expected_unit", "expected_step"),
    [
        pytest.param(0x4000, PERCENTAGE, "1.0", id="percent"),
        pytest.param(0x2000, "g/h", "0.1", id="grh"),
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
) -> None:
    """MBF_PAR_HIDRO unit, step and max follow the reported percent/g-h mode.

    ``MBF_PAR_UICFG_MACH_VISUAL_STYLE`` forces percentage (0x4000) or g/h
    (0x2000); the nominal (``MBF_PAR_HIDRO_NOM``) drives the maximum in both
    modes.
    """
    await setup_integration(hass, mock_config_entry_number)
    await _poll(
        hass,
        freezer,
        mock_neopool_client,
        {
            **MOCK_POOL_DATA,
            "MBF_PAR_HIDRO_NOM": 100,
            "MBF_PAR_MODEL": 0x0002,
            "MBF_PAR_UICFG_MACH_VISUAL_STYLE": visual_style,
        },
    )

    entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_hidro")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == expected_unit
    assert state.attributes["step"] == float(expected_step)
    assert state.attributes["max"] == 100


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


async def test_masked_number_write_passes_field_value(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Writing one masked number dispatches to async_set_masked_register.

    The read-modify-write that keeps the sibling byte intact is a lib concern
    (``async_set_masked_register`` performs it internally). The entity passes
    the *field value* (25 -> 50), not the packed 16-bit register.
    """
    mock_neopool_client.async_set_masked_register = AsyncMock(
        return_value={"MBF_PAR_HIDRO_COVER_REDUCTION": 0x0C32}
    )

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
    mock_neopool_client.async_set_masked_register.reset_mock()

    await _set_value(hass, cover_id, 50)
    await _flush(hass, freezer)

    mock_neopool_client.async_set_masked_register.assert_awaited_once_with(
        MaskedFlag.HIDRO_COVER_REDUCTION_PERCENT, 50
    )
    state = hass.states.get(cover_id)
    assert state is not None
    assert float(state.state) == 50


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
    await _set_value(hass, cover_id, 50)
    await _set_value(hass, shutdown_id, 20)
    await _flush(hass, freezer)

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
async def test_number_write_logs_communication_error(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    write_error: Exception,
) -> None:
    """Communication errors in the debounced write are logged, not raised.

    The debounced write runs after the service call returns, so raising would
    surface as an unhandled task exception. The next successful poll restores
    the entity state.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(side_effect=write_error)
    await setup_integration(hass, mock_config_entry_number)
    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")

    caplog.clear()
    await _set_value(hass, ph1_entity_id, 7.5)
    await _flush(hass, freezer)

    mock_neopool_client.async_set_setpoint.assert_awaited_once()
    assert "Failed to write" in caplog.text


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

    await _set_value(hass, ph1_entity_id, 7.0)
    await _set_value(hass, ph1_entity_id, 7.5)
    await _flush(hass, freezer)

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

    await _set_value(hass, ph1_entity_id, 7.0)
    await _advance(hass, freezer)
    await _set_value(hass, ph1_entity_id, 7.5)
    await _advance(hass, freezer)

    # 4s elapsed since the first click, but only 2s since the last: no write yet.
    mock_neopool_client.async_set_setpoint.assert_not_awaited()

    await _flush(hass, freezer)

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

    await _set_value(hass, ph1_entity_id, 8.0)
    await _set_value(hass, ph1_entity_id, 7.5)
    await _flush(hass, freezer)

    mock_neopool_client.async_set_setpoint.assert_not_awaited()
    state = hass.states.get(ph1_entity_id)
    assert state is not None
    assert float(state.state) == 7.5

    # Off-step request rounding to the same register: no write, and the UI must
    # snap back from the optimistic 7.504 to the device value.
    await _set_value(hass, ph1_entity_id, 7.504)
    await _flush(hass, freezer)

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
    """Unloading the entry cancels an un-elapsed debounced write."""
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    await _set_value(hass, ph1_entity_id, 7.5)

    # Unload before the cooldown elapses: the queued write must never fire.
    await hass.config_entries.async_unload(mock_config_entry_number.entry_id)
    await _flush(hass, freezer)

    mock_neopool_client.async_set_setpoint.assert_not_awaited()


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
    await _set_value(hass, ph1_entity_id, 7.5)

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

    mock_neopool_client.async_set_setpoint.assert_awaited_once()
    mock_update.assert_not_called()


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
