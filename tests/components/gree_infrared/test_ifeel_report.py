"""Tests for YAP1F I-Feel room temperature reports from a sensor."""

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from infrared_protocols.commands.gree_ac import GreeAcCommand, GreeAcIFeelReport
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from homeassistant.components.climate import HVACMode
from homeassistant.components.gree_infrared.climate import IFEEL_REPORT_INTERVAL
from homeassistant.components.gree_infrared.const import (
    CONF_HVAC_MODES,
    CONF_IFEEL_SENSOR_ENTITY_ID,
    DOMAIN,
    MODEL_GENERIC,
    MODEL_YAP1F,
)
from homeassistant.components.gree_infrared.state import COALESCE_DELAY_SEC
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_MODEL,
    STATE_UNAVAILABLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import ENTRY_ID

_CLIMATE = "climate.gree_ac"
_SENSOR = "sensor.room_temperature"


@pytest.fixture
def has_receiver() -> bool:
    """No receiver needed."""
    return False


@pytest.fixture
def extra_entry_data(hvac_modes: list[HVACMode]) -> dict[str, Any]:
    """Default to YAP1F with an I-Feel sensor."""
    return {
        CONF_HVAC_MODES: hvac_modes,
        CONF_MODEL: MODEL_YAP1F,
        CONF_IFEEL_SENSOR_ENTITY_ID: _SENSOR,
    }


def _set_sensor(
    hass: HomeAssistant, value: str, unit: str = UnitOfTemperature.CELSIUS
) -> None:
    hass.states.async_set(_SENSOR, value, {ATTR_UNIT_OF_MEASUREMENT: unit})


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.async_block_till_done()


async def _settle(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    await _tick(hass, freezer, timedelta(seconds=COALESCE_DELAY_SEC + 0.2))


async def _set_mode(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mode: HVACMode
) -> None:
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "hvac_mode": mode},
        blocking=True,
    )
    await _settle(hass, freezer)


async def _ifeel(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    on: bool,
) -> None:
    entity_id = entity_registry.async_get_entity_id(
        "switch", DOMAIN, f"{ENTRY_ID}_ifeel"
    )
    assert entity_id is not None
    await hass.services.async_call(
        "switch",
        "turn_on" if on else "turn_off",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await _settle(hass, freezer)


def _reports(emitter: MockInfraredEmitterEntity) -> list[int]:
    return [
        c.temperature
        for c in emitter.send_command_calls
        if isinstance(c, GreeAcIFeelReport)
    ]


async def _active(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    emitter: MockInfraredEmitterEntity,
) -> None:
    """Cool + I-Feel on, with the call log cleared."""
    await _set_mode(hass, freezer, HVACMode.COOL)
    await _ifeel(hass, entity_registry, freezer, True)
    emitter.send_command_calls.clear()


@pytest.mark.usefixtures("init_integration")
async def test_report_follows_frame(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Enabling I-Feel sends the state frame, then the report, in that order."""
    emitter = mock_infrared_emitter_entity
    _set_sensor(hass, "21.6")
    await _set_mode(hass, freezer, HVACMode.COOL)
    assert _reports(emitter) == []
    emitter.send_command_calls.clear()

    await _ifeel(hass, entity_registry, freezer, True)

    assert len(emitter.send_command_calls) == 2
    frame, report = emitter.send_command_calls
    assert isinstance(frame, GreeAcCommand)
    assert frame.ifeel is True
    assert isinstance(report, GreeAcIFeelReport)
    assert (
        report.get_raw_timings() == GreeAcIFeelReport(temperature=22).get_raw_timings()
    )


async def test_diagnostics_state_records_last_report(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """The last sent report value and time are kept for diagnostics."""
    _set_sensor(hass, "20")
    await _set_mode(hass, freezer, HVACMode.COOL)
    await _ifeel(hass, entity_registry, freezer, True)
    assert init_integration.runtime_data.last_ifeel_report == 20
    assert init_integration.runtime_data.last_ifeel_report_time is not None


@pytest.mark.usefixtures("init_integration")
async def test_sensor_change_reports_only_on_rounded_change(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """A change of the rounded value sends one report; sub-degree drift does not."""
    emitter = mock_infrared_emitter_entity
    _set_sensor(hass, "21.0")
    await _active(hass, entity_registry, freezer, emitter)

    _set_sensor(hass, "21.3")
    await hass.async_block_till_done()
    assert _reports(emitter) == []

    _set_sensor(hass, "23.2")
    await hass.async_block_till_done()
    assert _reports(emitter) == [23]


@pytest.mark.usefixtures("init_integration")
async def test_heartbeat(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """The report is repeated every ten minutes."""
    emitter = mock_infrared_emitter_entity
    _set_sensor(hass, "24")
    await _active(hass, entity_registry, freezer, emitter)

    await _tick(hass, freezer, IFEEL_REPORT_INTERVAL)
    assert _reports(emitter) == [24]
    await _tick(hass, freezer, IFEEL_REPORT_INTERVAL)
    assert _reports(emitter) == [24, 24]


@pytest.mark.usefixtures("init_integration")
async def test_no_report_when_ifeel_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """With I-Feel off, neither frames, changes nor heartbeats send reports."""
    emitter = mock_infrared_emitter_entity
    _set_sensor(hass, "24")
    await _set_mode(hass, freezer, HVACMode.COOL)
    _set_sensor(hass, "20")
    await _tick(hass, freezer, IFEEL_REPORT_INTERVAL)
    assert _reports(emitter) == []

    await _ifeel(hass, entity_registry, freezer, True)
    assert _reports(emitter) == [20]
    emitter.send_command_calls.clear()
    await _ifeel(hass, entity_registry, freezer, False)
    _set_sensor(hass, "18")
    await _tick(hass, freezer, IFEEL_REPORT_INTERVAL)
    assert _reports(emitter) == []


@pytest.mark.usefixtures("init_integration")
async def test_no_report_when_unit_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """A powered-off unit gets no reports, even with I-Feel left on."""
    emitter = mock_infrared_emitter_entity
    _set_sensor(hass, "24")
    await _active(hass, entity_registry, freezer, emitter)
    await _set_mode(hass, freezer, HVACMode.OFF)
    emitter.send_command_calls.clear()

    _set_sensor(hass, "19")
    await _tick(hass, freezer, IFEEL_REPORT_INTERVAL)
    assert _reports(emitter) == []


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("bad_state", [STATE_UNAVAILABLE, "unknown", "warm"])
async def test_unusable_sensor_skipped(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    bad_state: str,
) -> None:
    """Unavailable, unknown and non-numeric readings send nothing."""
    emitter = mock_infrared_emitter_entity
    _set_sensor(hass, "24")
    await _active(hass, entity_registry, freezer, emitter)

    _set_sensor(hass, bad_state)
    await _tick(hass, freezer, IFEEL_REPORT_INTERVAL)
    assert _reports(emitter) == []


async def test_missing_sensor_state_skipped(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """A sensor that has no state yet is skipped without error."""
    emitter = mock_infrared_emitter_entity
    await _active(hass, entity_registry, freezer, emitter)
    await _tick(hass, freezer, IFEEL_REPORT_INTERVAL)
    assert _reports(emitter) == []


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        ("75.2", UnitOfTemperature.FAHRENHEIT, 24),
        ("297.15", UnitOfTemperature.KELVIN, 24),
        ("-5", UnitOfTemperature.CELSIUS, 0),
        ("80", UnitOfTemperature.CELSIUS, 50),
    ],
)
async def test_conversion_and_clamp(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    value: str,
    unit: str,
    expected: int,
) -> None:
    """Fahrenheit readings are converted; the value is clamped to 0..50."""
    emitter = mock_infrared_emitter_entity
    _set_sensor(hass, value, unit)
    await _set_mode(hass, freezer, HVACMode.COOL)
    emitter.send_command_calls.clear()
    await _ifeel(hass, entity_registry, freezer, True)
    assert _reports(emitter) == [expected]


@pytest.mark.parametrize(
    "extra_entry_data",
    [
        {
            CONF_HVAC_MODES: [HVACMode.COOL],
            CONF_MODEL: MODEL_GENERIC,
            CONF_IFEEL_SENSOR_ENTITY_ID: _SENSOR,
        }
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_generic_model_never_reports(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """The generic model has no I-Feel and never sends reports."""
    emitter = mock_infrared_emitter_entity
    assert (
        entity_registry.async_get_entity_id("switch", DOMAIN, f"{ENTRY_ID}_ifeel")
        is None
    )
    _set_sensor(hass, "24")
    await _set_mode(hass, freezer, HVACMode.COOL)
    _set_sensor(hass, "19")
    await _tick(hass, freezer, IFEEL_REPORT_INTERVAL)
    assert _reports(emitter) == []


@pytest.mark.parametrize(
    "extra_entry_data",
    [{CONF_HVAC_MODES: [HVACMode.COOL], CONF_MODEL: MODEL_YAP1F}],
)
@pytest.mark.usefixtures("init_integration")
async def test_no_sensor_never_reports(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """A YAP1F entry without a sensor turns I-Feel on but never reports."""
    emitter = mock_infrared_emitter_entity
    _set_sensor(hass, "24")
    await _set_mode(hass, freezer, HVACMode.COOL)
    emitter.send_command_calls.clear()
    await _ifeel(hass, entity_registry, freezer, True)
    assert (
        entity_registry.async_get_entity_id("switch", DOMAIN, f"{ENTRY_ID}_ifeel")
        is not None
    )
    assert len(emitter.send_command_calls) == 1
    assert emitter.send_command_calls[0].ifeel is True
    _set_sensor(hass, "19")
    await _tick(hass, freezer, IFEEL_REPORT_INTERVAL)
    assert _reports(emitter) == []


@pytest.mark.usefixtures("init_integration")
async def test_recovery_at_same_value_reports(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Coming back from an unusable reading at the same value reports at once."""
    emitter = mock_infrared_emitter_entity
    _set_sensor(hass, "24")
    await _active(hass, entity_registry, freezer, emitter)
    _set_sensor(hass, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert _reports(emitter) == []
    _set_sensor(hass, "24.2")
    await hass.async_block_till_done()
    assert _reports(emitter) == [24]


@pytest.mark.usefixtures("init_integration")
async def test_queued_report_not_sent_after_unload(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """A report queued behind the lock is dropped when the entry unloads."""
    emitter = mock_infrared_emitter_entity
    _set_sensor(hass, "24")
    await _active(hass, entity_registry, freezer, emitter)

    async with init_integration.runtime_data.command_lock:
        _set_sensor(hass, "20")
        await asyncio.sleep(0)
        unload = hass.async_create_task(
            hass.config_entries.async_unload(init_integration.entry_id)
        )
        await asyncio.sleep(0)
    assert await unload
    await hass.async_block_till_done()
    assert _reports(emitter) == []

    _set_sensor(hass, "30")
    await _tick(hass, freezer, IFEEL_REPORT_INTERVAL)
    assert _reports(emitter) == []


async def test_sensor_registry_id_is_resolved(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: Any,
) -> None:
    """A sensor stored as an entity registry id is resolved to its entity_id."""
    entry = entity_registry.async_get_or_create(
        "sensor", "test", "room", suggested_object_id="room_temperature"
    )
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_IFEEL_SENSOR_ENTITY_ID: entry.id},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    emitter = mock_infrared_emitter_entity
    _set_sensor(hass, "22")
    await _set_mode(hass, freezer, HVACMode.COOL)
    emitter.send_command_calls.clear()
    await _ifeel(hass, entity_registry, freezer, True)
    assert _reports(emitter) == [22]


@pytest.mark.usefixtures("init_integration")
async def test_report_failure_does_not_break_frames(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failing report is logged and the next frame is still sent."""
    emitter = mock_infrared_emitter_entity
    _set_sensor(hass, "24")
    await _active(hass, entity_registry, freezer, emitter)

    real_send = emitter.async_send_command

    async def _fail_reports(command: Any) -> None:
        if isinstance(command, GreeAcIFeelReport):
            raise HomeAssistantError("boom")
        await real_send(command)

    with patch.object(emitter, "async_send_command", side_effect=_fail_reports):
        _set_sensor(hass, "20")
        await hass.async_block_till_done()
        await _tick(hass, freezer, IFEEL_REPORT_INTERVAL)
    assert "I-Feel report send failed" in caplog.text
    assert _reports(emitter) == []

    await _set_mode(hass, freezer, HVACMode.DRY)
    assert isinstance(emitter.send_command_calls[-2], GreeAcCommand)
    assert _reports(emitter) == [20]


async def test_sensor_rename_is_followed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: Any,
) -> None:
    """Renaming the sensor entity rebinds tracking to the new entity id."""
    entity_registry.async_get_or_create(
        "sensor", "test", "room", suggested_object_id="room_temperature"
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    emitter = mock_infrared_emitter_entity
    _set_sensor(hass, "22")
    await _active(hass, entity_registry, freezer, emitter)

    entity_registry.async_update_entity(_SENSOR, new_entity_id="sensor.renamed")
    await hass.async_block_till_done()
    hass.states.async_set(
        "sensor.renamed", "25", {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    await hass.async_block_till_done()
    assert _reports(emitter) == [25]

    _set_sensor(hass, "30")
    await hass.async_block_till_done()
    assert _reports(emitter) == [25]
    await _tick(hass, freezer, IFEEL_REPORT_INTERVAL)
    assert _reports(emitter) == [25, 25]


@pytest.mark.usefixtures("init_integration")
async def test_pending_reports_coalesce(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Changes queued behind the lock produce one report with the latest value."""
    emitter = mock_infrared_emitter_entity
    _set_sensor(hass, "20")
    await _active(hass, entity_registry, freezer, emitter)

    async with init_integration.runtime_data.command_lock:
        for value in ("21", "22", "23"):
            _set_sensor(hass, value)
            await asyncio.sleep(0)
    await hass.async_block_till_done()
    assert _reports(emitter) == [23]


@pytest.mark.usefixtures("init_integration")
async def test_no_listener_report_before_enabling_frame(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Staged I-Feel is not live until its frame is sent."""
    emitter = mock_infrared_emitter_entity
    _set_sensor(hass, "20")
    await _set_mode(hass, freezer, HVACMode.COOL)
    emitter.send_command_calls.clear()

    entity_id = entity_registry.async_get_entity_id(
        "switch", DOMAIN, f"{ENTRY_ID}_ifeel"
    )
    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    _set_sensor(hass, "23")
    await hass.async_block_till_done()
    assert emitter.send_command_calls == []

    await _settle(hass, freezer)
    assert [type(c) for c in emitter.send_command_calls] == [
        GreeAcCommand,
        GreeAcIFeelReport,
    ]
    assert _reports(emitter) == [23]


@pytest.mark.usefixtures("init_integration")
async def test_failed_enabling_frame_sends_no_reports(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """If the frame enabling I-Feel fails, heartbeats and changes stay silent."""
    emitter = mock_infrared_emitter_entity
    _set_sensor(hass, "20")
    await _set_mode(hass, freezer, HVACMode.COOL)
    emitter.send_command_calls.clear()

    with patch.object(
        emitter, "async_send_command", side_effect=HomeAssistantError("boom")
    ):
        await _ifeel(hass, entity_registry, freezer, True)
    _set_sensor(hass, "24")
    await _tick(hass, freezer, IFEEL_REPORT_INTERVAL)
    assert emitter.send_command_calls == []
