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
from homeassistant.const import PERCENTAGE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform as ep, entity_registry as er

from . import setup_integration
from .conftest import MOCK_POOL_DATA

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


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


def _disable_debounce(hass: HomeAssistant) -> None:
    """Set ``_debounce_delay = 0`` on every number entity so writes run at once."""
    for platforms in ep.async_get_platforms(hass, "neopool"):
        for ent in platforms.entities.values():
            if ent.entity_id.startswith("number."):
                ent._debounce_delay = 0


async def _flush_debounce(hass: HomeAssistant, entity_obj) -> None:
    """Wait for the entity's pending debounced write task to complete."""
    task = getattr(entity_obj, "_pending_write_task", None)
    if task is None:
        return
    await asyncio.wait_for(task, timeout=1)
    await hass.async_block_till_done()


def _entity_by_id(hass: HomeAssistant, entity_id: str):
    """Return the loaded entity object for a given entity_id."""
    for platforms in ep.async_get_platforms(hass, "neopool"):
        for ent in platforms.entities.values():
            if ent.entity_id == entity_id:
                return ent
    return None


async def test_simple_number_writes_register_after_debounce(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Setting a numeric value dispatches to the correct lib high-level API.

    Covers the ``async_set_setpoint`` path used by every number entity,
    including SMART_TEMP_HIGH/LOW which route through
    ``SetpointKind.SMART_TEMP_HIGH/LOW`` since lib 4.1.0.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )

    await setup_integration(hass, mock_config_entry_number)
    _disable_debounce(hass)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    mock_neopool_client.async_set_setpoint.reset_mock()

    await _set_value(hass, ph1_entity_id, 7.5)

    ph1_obj = _entity_by_id(hass, ph1_entity_id)
    await _flush_debounce(hass, ph1_obj)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.PH_MAX, 750
    )

    smart_entity_id = _number_entity_id(
        hass, mock_config_entry_number, "mbf_par_smart_temp_high"
    )
    mock_neopool_client.async_set_setpoint.reset_mock()

    await _set_value(hass, smart_entity_id, 30.0)

    smart_obj = _entity_by_id(hass, smart_entity_id)
    await _flush_debounce(hass, smart_obj)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.SMART_TEMP_HIGH, 30
    )


async def test_scaled_setpoint_optimistic_value_is_ui_scaled(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Optimistic native_value after a scaled setpoint write is UI-scaled.

    The lib override carries the raw register value (7.5 pH -> 750), but
    native_value must read back the decoded value. Regression guard: the
    merged optimistic value must surface as 7.5, not 750. The refresh poll
    is stubbed out so it cannot mask the merge.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )

    await setup_integration(hass, mock_config_entry_number)
    _disable_debounce(hass)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    ph1_obj = _entity_by_id(hass, ph1_entity_id)

    with patch.object(ph1_obj.coordinator, "async_request_refresh", AsyncMock()):
        await _set_value(hass, ph1_entity_id, 7.5)
        await _flush_debounce(hass, ph1_obj)

    assert ph1_obj.native_value == 7.5


async def test_pending_value_shown_optimistically_before_write(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """native_value surfaces the pending value while the debounce is in flight.

    Until the debounced write merges the override, the coordinator still holds
    the old register. The entity must report the requested value optimistically
    so the UI does not snap back to the stale reading.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    ph1_obj = _entity_by_id(hass, ph1_entity_id)
    ph1_obj._debounce_delay = 5.0

    await ph1_obj.async_set_native_value(7.5)
    task = ph1_obj._pending_write_task
    assert task is not None and not task.done()

    assert ph1_obj.native_value == 7.5
    mock_neopool_client.async_set_setpoint.assert_not_awaited()

    task.cancel()
    await hass.async_block_till_done()


async def test_scaled_write_rounds_to_nearest_register_int(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """The scaled register value is rounded, not truncated.

    Regression guard: ``4.1 * 100`` evaluates to ``409.999...`` in float, so a
    plain ``int()`` would write 409. The write must round to 410.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 410}
    )
    await setup_integration(hass, mock_config_entry_number)
    _disable_debounce(hass)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    ph1_obj = _entity_by_id(hass, ph1_entity_id)

    mock_neopool_client.async_set_setpoint.reset_mock()
    await _set_value(hass, ph1_entity_id, 4.1)
    await _flush_debounce(hass, ph1_obj)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.PH_MAX, 410
    )


async def test_heating_setpoint_mirrors_to_intelligent(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Writing the heating setpoint delegates to async_set_setpoint(HEATING).

    Since lib v4 the number entity no longer talks to ``async_set_temp_setpoint``;
    the high-level ``async_set_setpoint`` API owns the write and returns the
    optimistic-update dict the coordinator merges in. The heating<->intelligent
    mirror lives in the coordinator's ``_sync_heating_intelligent_setpoints``
    and fires on the *next* refresh cycle, not from the entity itself.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_HEATING_TEMP": 28}
    )

    await setup_integration(hass, mock_config_entry_number)
    _disable_debounce(hass)
    entity_id = _number_entity_id(
        hass, mock_config_entry_number, "mbf_par_heating_temp"
    )

    mock_neopool_client.async_set_setpoint.reset_mock()
    await _set_value(hass, entity_id, 28.0)

    entity_obj = _entity_by_id(hass, entity_id)
    await _flush_debounce(hass, entity_obj)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.HEATING, 28
    )


async def test_number_native_value_returns_rounded_raw(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """native_value returns round(raw, 2) when coordinator has the register."""
    await setup_integration(hass, mock_config_entry_number)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_PH1": 7.55,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_obj = None
    for platforms in ep.async_get_platforms(hass, "neopool"):
        for ent in platforms.entities.values():
            if (
                ent.entity_id.startswith("number.")
                and getattr(ent, "_data_key", None) == "MBF_PAR_PH1"
            ):
                entity_obj = ent
                break
        if entity_obj is not None:
            break
    if entity_obj is None:
        pytest.skip("MBF_PAR_PH1 number entity not registered")
    assert entity_obj.native_value == 7.55


async def test_native_value_zero_precision_rounds_to_int(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A zero-precision entity rounds its coordinator value to a whole number."""
    await setup_integration(hass, mock_config_entry_number)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_HEATING_TEMP": 27.6,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_obj = None
    for platforms in ep.async_get_platforms(hass, "neopool"):
        for ent in platforms.entities.values():
            if (
                ent.entity_id.startswith("number.")
                and getattr(ent.entity_description, "key", None)
                == "MBF_PAR_HEATING_TEMP"
            ):
                entity_obj = ent
                break
        if entity_obj is not None:
            break
    if entity_obj is None:
        pytest.skip("MBF_PAR_HEATING_TEMP number entity not registered")
    assert entity_obj.suggested_display_precision == 0
    assert entity_obj.native_value == 28.0


@pytest.mark.parametrize(
    ("visual_style", "expected_unit", "expected_step", "expected_precision"),
    [
        pytest.param(0x4000, PERCENTAGE, 1.0, 0, id="percent"),
        pytest.param(0x2000, "g/h", 0.1, 1, id="grh"),
    ],
)
async def test_hidro_native_value_units_follow_visual_style(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    visual_style: int,
    expected_unit: str,
    expected_step: float,
    expected_precision: int,
) -> None:
    """MBF_PAR_HIDRO unit, step and precision follow the reported percent/g-h mode.

    ``MBF_PAR_UICFG_MACH_VISUAL_STYLE`` forces percentage (0x4000) or g/h
    (0x2000); the nominal (``MBF_PAR_HIDRO_NOM``) drives native_max_value in
    both modes.
    """
    await setup_integration(hass, mock_config_entry_number)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_HIDRO_NOM": 100,
        "MBF_PAR_MODEL": 0x0002,
        "MBF_PAR_UICFG_MACH_VISUAL_STYLE": visual_style,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_obj = None
    for platforms in ep.async_get_platforms(hass, "neopool"):
        for ent in platforms.entities.values():
            if (
                ent.entity_id.startswith("number.")
                and getattr(ent.entity_description, "key", None) == "MBF_PAR_HIDRO"
            ):
                entity_obj = ent
                break
        if entity_obj is not None:
            break
    if entity_obj is None:
        pytest.skip("MBF_PAR_HIDRO entity not registered on this fixture")
    assert entity_obj.native_max_value == 100
    assert entity_obj.native_unit_of_measurement == expected_unit
    assert entity_obj.native_step == expected_step
    assert entity_obj.suggested_display_precision == expected_precision


async def test_masked_number_native_value_decodes_via_mask_shift(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that masked compound numbers decode via _mask/_shift.

    HIDRO_COVER_REDUCTION / SHUTDOWN_TEMPERATURE share register 0x042D,
    lower byte holds cover reduction %, upper byte the shutdown
    temperature. native_value must isolate each via _mask/_shift.
    """
    await setup_integration(hass, mock_config_entry_number)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_HIDRO_COVER_REDUCTION": 0x0C19,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    cover, shutdown = None, None
    for platforms in ep.async_get_platforms(hass, "neopool"):
        for ent in platforms.entities.values():
            key = getattr(ent.entity_description, "key", None)
            if not ent.entity_id.startswith("number."):
                continue
            if key == "MBF_PAR_HIDRO_COVER_REDUCTION":
                cover = ent
            elif key == "MBF_PAR_HIDRO_SHUTDOWN_TEMPERATURE":
                shutdown = ent
    if cover is None or shutdown is None:
        pytest.skip("masked numbers not registered on this fixture")
    assert cover.native_value == 25
    assert shutdown.native_value == 12


async def test_masked_number_write_preserves_other_byte(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Writing one masked number dispatches to async_set_masked_register.

    The read-modify-write that keeps the sibling byte intact is now a lib
    concern (``async_set_masked_register`` performs it internally). The
    custom entity must therefore pass the *field value* (25 → 50), not the
    packed 16-bit register, to the high-level API.
    """
    mock_neopool_client.async_set_masked_register = AsyncMock(
        return_value={"MBF_PAR_HIDRO_COVER_REDUCTION": 0x0C32}
    )

    await setup_integration(hass, mock_config_entry_number)
    _disable_debounce(hass)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_HIDRO_COVER_REDUCTION": 0x0C19,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    cover_entity_id = None
    cover_obj = None
    for platforms in ep.async_get_platforms(hass, "neopool"):
        for ent in platforms.entities.values():
            if (
                ent.entity_id.startswith("number.")
                and getattr(ent.entity_description, "key", None)
                == "MBF_PAR_HIDRO_COVER_REDUCTION"
            ):
                cover_entity_id = ent.entity_id
                cover_obj = ent
    if cover_entity_id is None:
        pytest.skip("MBF_PAR_HIDRO_COVER_REDUCTION entity not registered")

    mock_neopool_client.async_set_masked_register.reset_mock()
    await _set_value(hass, cover_entity_id, 50)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_HIDRO_COVER_REDUCTION": 0x0C32,
    }
    await _flush_debounce(hass, cover_obj)

    mock_neopool_client.async_set_masked_register.assert_awaited_once_with(
        MaskedFlag.HIDRO_COVER_REDUCTION_PERCENT, 50
    )
    assert cover_obj.native_value == 50


@pytest.mark.parametrize(
    "write_error",
    [
        pytest.param(NeoPoolConnectionError("boom"), id="lib-connection-error"),
        pytest.param(TimeoutError("boom"), id="timeout"),
        pytest.param(OSError("boom"), id="os-error"),
    ],
)
async def test_number_debounced_write_logs_communication_error(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
    write_error: Exception,
) -> None:
    """Communication errors in the debounced write are logged, not raised.

    The debounced write runs as a background task, so raising would surface
    as an unhandled task exception. The next successful poll restores the
    entity state.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(side_effect=write_error)
    await setup_integration(hass, mock_config_entry_number)
    _disable_debounce(hass)
    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    ph1_obj = _entity_by_id(hass, ph1_entity_id)

    caplog.clear()
    await _set_value(hass, ph1_entity_id, 7.5)
    await _flush_debounce(hass, ph1_obj)

    mock_neopool_client.async_set_setpoint.assert_awaited_once()
    assert "Failed to write" in caplog.text


async def test_repeated_set_value_cancels_pending_task(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A second set_value cancels the first pending task; only the latest writes."""
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 700}
    )
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    ph1_obj = _entity_by_id(hass, ph1_entity_id)
    ph1_obj._debounce_delay = 0.05

    mock_neopool_client.async_set_setpoint.reset_mock()
    await ph1_obj.async_set_native_value(7.0)
    first_task = ph1_obj._pending_write_task
    await ph1_obj.async_set_native_value(7.5)
    assert first_task is not None
    await hass.async_block_till_done()
    assert first_task.cancelled()
    await _flush_debounce(hass, ph1_obj)

    mock_neopool_client.async_set_setpoint.assert_awaited_once_with(
        SetpointKind.PH_MAX, 750
    )


async def test_pending_write_cancelled_on_remove(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Removing the entity cancels and awaits an in-flight debounced write."""
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    ph1_obj = _entity_by_id(hass, ph1_entity_id)
    ph1_obj._debounce_delay = 5.0

    await ph1_obj.async_set_native_value(7.5)
    task = ph1_obj._pending_write_task
    assert task is not None and not task.done()

    await ph1_obj.async_will_remove_from_hass()
    assert task.done()
    mock_neopool_client.async_set_setpoint.assert_not_awaited()


async def test_cancelled_debounce_swallows_cancelled_error(
    hass: HomeAssistant,
    mock_config_entry_number: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Cancelling a write already inside the debounce sleep is swallowed cleanly.

    The task must be running its ``asyncio.sleep`` when cancelled so the
    ``except asyncio.CancelledError`` branch in ``_debounced_write`` handles it,
    rather than the task being cancelled before its body starts.
    """
    mock_neopool_client.async_set_setpoint = AsyncMock(
        return_value={"MBF_PAR_PH1": 750}
    )
    await setup_integration(hass, mock_config_entry_number)

    ph1_entity_id = _number_entity_id(hass, mock_config_entry_number, "mbf_par_ph1")
    ph1_obj = _entity_by_id(hass, ph1_entity_id)
    ph1_obj._debounce_delay = 5.0

    await ph1_obj.async_set_native_value(7.5)
    task = ph1_obj._pending_write_task
    assert task is not None
    await asyncio.sleep(0)
    task.cancel()
    await hass.async_block_till_done()

    assert task.done() and not task.cancelled()
    mock_neopool_client.async_set_setpoint.assert_not_awaited()


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
