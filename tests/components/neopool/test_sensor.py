"""Tests for the NeoPool sensor platform."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import ATTR_OPTIONS
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import MOCK_POOL_DATA


async def test_measurement_sensors_suppressed_when_filtration_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Probe sensors report unknown while filtration pump is off (stale reading)."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Filtration Pump": False,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    for entity_id in (
        "sensor.neopool_ph",
        "sensor.neopool_redox_potential",
        "sensor.neopool_water_temperature",
    ):
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} not registered"
        assert state.state == "unknown"


async def test_production_sensors_zero_when_filtration_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Production sensors report 0 while filtration pump is off (cell idle)."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Filtration Pump": False,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    for entity_id in (
        "sensor.neopool_hydrolysis_intensity",
        "sensor.neopool_ionization_level",
    ):
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} not registered"
        assert state.state == "0"


@pytest.mark.parametrize(
    ("filt_mode", "expected"),
    [
        (0, "manual"),
        (1, "auto"),
        (2, "heating"),
        (3, "smart"),
        (4, "intelligent"),
        (13, "backwash"),
    ],
)
async def test_filt_mode_native_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    filt_mode: int,
    expected: str,
) -> None:
    """Filt mode native value reads the lib's decoded filtration_mode key."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILT_MODE": filt_mode,
        "filtration_mode": expected,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.neopool_filtration_mode")
    assert state is not None
    assert state.state == expected


@pytest.mark.parametrize(
    ("relay", "expected_options"),
    [
        pytest.param(1, ["off", "idle", "acid"], id="acid_only"),
        pytest.param(2, ["off", "idle", "base"], id="base_only"),
        pytest.param(0, ["off", "idle", "acid", "base", "both"], id="both_relays"),
    ],
)
async def test_ph_pump_status_options_per_relay_config(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    relay: int,
    expected_options: list[str],
) -> None:
    """The pH pump status options list shrinks based on the relay configuration."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_RELAY_PH": relay,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.neopool_ph_pump_status")
    assert state is not None
    assert state.attributes[ATTR_OPTIONS] == expected_options


async def test_hidro_current_g_per_hour_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """In g/h mode HIDRO_CURRENT swaps unit and bumps display precision."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_UICFG_MACHINE": 1,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.neopool_hydrolysis_intensity")
    assert state is not None
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "g/h"


_CELL_RUNTIME_ENTITY_IDS: dict[str, str] = {
    "CELL_RUNTIME_TOTAL": "sensor.neopool_cell_runtime_total",
    "CELL_RUNTIME_PART": "sensor.neopool_cell_runtime_since_reset",
    "CELL_RUNTIME_POLA": "sensor.neopool_cell_runtime_in_polarity_1",
    "CELL_RUNTIME_POLB": "sensor.neopool_cell_runtime_in_polarity_2",
    "CELL_RUNTIME_POL_CHANGES": "sensor.neopool_cell_polarity_changes",
}


@pytest.mark.parametrize(
    ("key", "expected_seconds"),
    [
        ("CELL_RUNTIME_TOTAL", 65536),
        ("CELL_RUNTIME_PART", 3600),
        ("CELL_RUNTIME_POLA", 1800),
        ("CELL_RUNTIME_POLB", 1800),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_neopool_client")
async def test_cell_runtime_duration_sensor_reads_combined_register(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    key: str,
    expected_seconds: int,
) -> None:
    """Each duration CELL_RUNTIME_* sensor reads the combined u32 key from coordinator data.

    Sensors have ``entity_registry_enabled_default=False``; enabling every
    disabled-by-default entity via the fixture avoids the reload dance. The
    sensors declare seconds but suggest hours, so ``state.state`` is expressed
    in hours (converted by the frontend layer).
    """
    await setup_integration(hass, mock_config_entry)

    entity_id = _CELL_RUNTIME_ENTITY_IDS[key]
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} not registered"
    assert float(state.state) == pytest.approx(expected_seconds / 3600, abs=1e-4)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_neopool_client")
async def test_cell_runtime_pol_changes_sensor_reads_combined_register(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """CELL_RUNTIME_POL_CHANGES reads the combined u32 key as a raw counter.

    Unlike the duration sensors, this one has no unit and no unit conversion,
    so ``state.state`` is the raw integer from coordinator data.
    """
    await setup_integration(hass, mock_config_entry)

    entity_id = _CELL_RUNTIME_ENTITY_IDS["CELL_RUNTIME_POL_CHANGES"]
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} not registered"
    assert state.state == "7"


@pytest.mark.freeze_time("2026-07-03T12:00:00Z")
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_neopool_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot every entity registered by the sensor platform."""
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2026-07-03T12:00:00Z")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_when_modules_absent(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    minimal_pool_data: dict[str, Any],
) -> None:
    """Snapshot the sensor entities registered when no modules are present."""
    mock_neopool_client.async_read_all.return_value = minimal_pool_data
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_filtration_remaining_aggregates_timer_countdowns(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """FILTRATION_REMAINING reports the largest positive filtration countdown.

    The aggregation lives in the library; the coordinator stores the countdown
    seconds under FILTRATION_REMAINING and the sensor renders them as the
    absolute end timestamp (now + remaining).
    """

    def _timers(
        enabled_timers: list[str] | None = None, **_kwargs: object
    ) -> dict[str, dict[str, object]]:
        countdowns = {"filtration1": 1800, "filtration2": 3600, "filtration3": 0}
        return {
            name: {
                "enable": 1,
                "on": 0,
                "interval": 0,
                "period": 0,
                "countdown": countdowns.get(name, 0),
                "stop": None,
            }
            for name in (enabled_timers or [])
        }

    mock_neopool_client.read_all_timers.side_effect = _timers
    await setup_integration(hass, mock_config_entry)
    # The sensor's context registers after setup; poll again so the coordinator
    # reads the filtration blocks and aggregates their countdown.
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.neopool_filtration_time_remaining")
    assert state is not None
    # Largest countdown (3600s) as an end time, truncated to whole seconds.
    expected = (dt_util.utcnow() + timedelta(seconds=3600)).replace(microsecond=0)
    assert state.state == expected.isoformat()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_filtration_remaining_unknown_when_not_counting_down(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """With no positive countdown, the end time is unknown, not a stale value."""

    def _timers(
        enabled_timers: list[str] | None = None, **_kwargs: object
    ) -> dict[str, dict[str, object]]:
        return {
            name: {
                "enable": 1,
                "on": 0,
                "interval": 0,
                "period": 0,
                "countdown": 0,
                "stop": None,
            }
            for name in (enabled_timers or [])
        }

    mock_neopool_client.read_all_timers.side_effect = _timers
    await setup_integration(hass, mock_config_entry)
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.neopool_filtration_time_remaining")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_filtration_remaining_holds_steady_within_variance(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A countdown ticking down in step with the clock keeps one stable end time.

    Per-second drift stays within tolerance, so the end time only moves on a
    real change.
    """
    countdown = {"value": 3600}

    def _timers(
        enabled_timers: list[str] | None = None, **_kwargs: object
    ) -> dict[str, dict[str, object]]:
        return {
            name: {
                "enable": 1,
                "on": 0,
                "interval": 0,
                "period": 0,
                "countdown": countdown["value"],
                "stop": None,
            }
            for name in (enabled_timers or [])
        }

    mock_neopool_client.read_all_timers.side_effect = _timers
    await setup_integration(hass, mock_config_entry)
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    first = hass.states.get("sensor.neopool_filtration_time_remaining")
    assert first is not None

    # 20s later the device reports 20s less, landing on the same end. Hold it.
    countdown["value"] = 3580
    freezer.tick(timedelta(seconds=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    second = hass.states.get("sensor.neopool_filtration_time_remaining")
    assert second is not None
    assert second.state == first.state

    # A real jump beyond the tolerance (pump restarted) moves the end time.
    countdown["value"] = 7200
    freezer.tick(timedelta(seconds=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    third = hass.states.get("sensor.neopool_filtration_time_remaining")
    assert third is not None
    assert third.state != first.state


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_filtration_remaining_resets_after_countdown_stops(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A new countdown after a stop is not masked by the held end time.

    A short new countdown can land within the tolerance of the stopped one, so
    the held end time must be dropped on the stop, not reused.
    """
    countdown = {"value": 20}

    def _timers(
        enabled_timers: list[str] | None = None, **_kwargs: object
    ) -> dict[str, dict[str, object]]:
        return {
            name: {
                "enable": 1,
                "on": 0,
                "interval": 0,
                "period": 0,
                "countdown": countdown["value"],
                "stop": None,
            }
            for name in (enabled_timers or [])
        }

    mock_neopool_client.read_all_timers.side_effect = _timers
    await setup_integration(hass, mock_config_entry)
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.neopool_filtration_time_remaining") is not None

    # Countdown stops.
    countdown["value"] = 0
    freezer.tick(timedelta(seconds=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    stopped = hass.states.get("sensor.neopool_filtration_time_remaining")
    assert stopped is not None
    assert stopped.state == STATE_UNKNOWN

    # A new short countdown whose end falls within the tolerance of the stopped
    # one must be reported fresh, not held over.
    countdown["value"] = 5
    freezer.tick(timedelta(seconds=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    restarted = hass.states.get("sensor.neopool_filtration_time_remaining")
    assert restarted is not None
    expected = (dt_util.utcnow() + timedelta(seconds=5)).replace(microsecond=0)
    assert restarted.state == expected.isoformat()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_filtration_remaining_takes_new_end_when_held_one_expired(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A restart without a zero reading is not masked by an expired end time.

    A countdown that restarts between polls can report the same short value
    twice; the held end time has expired by then and must not be held over,
    even though the new end falls within the tolerance.
    """
    countdown = {"value": 10}

    def _timers(
        enabled_timers: list[str] | None = None, **_kwargs: object
    ) -> dict[str, dict[str, object]]:
        return {
            name: {
                "enable": 1,
                "on": 0,
                "interval": 0,
                "period": 0,
                "countdown": countdown["value"],
                "stop": None,
            }
            for name in (enabled_timers or [])
        }

    mock_neopool_client.read_all_timers.side_effect = _timers
    await setup_integration(hass, mock_config_entry)
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    first = hass.states.get("sensor.neopool_filtration_time_remaining")
    assert first is not None

    # 20s later the same 10s countdown is reported again (a restart). The held
    # end time is now 10s in the past, so the new one must be taken.
    freezer.tick(timedelta(seconds=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    second = hass.states.get("sensor.neopool_filtration_time_remaining")
    assert second is not None
    expected = (dt_util.utcnow() + timedelta(seconds=10)).replace(microsecond=0)
    assert second.state == expected.isoformat()
    assert second.state != first.state


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_filtration_remaining_polls_filtration_blocks_when_enabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Enabling the sensor registers all three filtration blocks for polling.

    Only the sensor platform is loaded, so no filtration time entity registers
    a block context. The three blocks can only reach the read through the
    sensor's own context, which makes this test catch the context plumbing
    being dropped.
    """
    calls: list[list[str] | None] = []

    def _capture(
        enabled_timers: list[str] | None = None, **_kwargs: object
    ) -> dict[str, dict[str, object]]:
        calls.append(enabled_timers)
        return {
            name: {
                "enable": 1,
                "on": 0,
                "interval": 0,
                "period": 0,
                "countdown": 0,
                "stop": None,
            }
            for name in (enabled_timers or [])
        }

    mock_neopool_client.read_all_timers.side_effect = _capture
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    enabled_timers = calls[-1]
    assert enabled_timers is not None
    assert "filtration1" in enabled_timers
    assert "filtration2" in enabled_timers
    assert "filtration3" in enabled_timers


def _capture_force_read(
    mock_neopool_client: MagicMock,
    countdown: int = 0,
) -> list[tuple[str, ...] | None]:
    """Record the force_read argument of every read_all_timers call."""
    calls: list[tuple[str, ...] | None] = []

    def _capture(
        enabled_timers: list[str] | None = None,
        force_read: tuple[str, ...] | None = None,
    ) -> dict[str, dict[str, object]]:
        calls.append(force_read)
        return {
            name: {
                "enable": 1,
                "on": 0,
                "interval": 0,
                "period": 0,
                "countdown": countdown,
                "stop": None,
            }
            for name in (enabled_timers or [])
        }

    mock_neopool_client.read_all_timers.side_effect = _capture
    return calls


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_filtration_remaining_force_reads_blocks_while_pump_runs(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """With the sensor enabled and the pump on, filtration blocks bypass the cache."""
    calls = _capture_force_read(mock_neopool_client)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Filtration Pump": True,
    }
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    force_read = calls[-1]
    assert force_read is not None
    assert set(force_read) == {"filtration1", "filtration2", "filtration3"}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_filtration_remaining_force_reads_after_pump_off_with_countdown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A positive previous countdown keeps blocks force-read after the pump stops."""
    # First poll with the pump on and a positive countdown seeds FILTRATION_REMAINING.
    calls = _capture_force_read(mock_neopool_client, countdown=600)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Filtration Pump": True,
    }
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Pump turns off, but the previous countdown was positive, so the next poll
    # still force-reads to catch the final tick.
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Filtration Pump": False,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    force_read = calls[-1]
    assert force_read is not None
    assert set(force_read) == {"filtration1", "filtration2", "filtration3"}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_filtration_remaining_no_force_read_when_idle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """With the sensor enabled but pump off and no countdown, nothing is force-read."""
    calls = _capture_force_read(mock_neopool_client, countdown=0)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Filtration Pump": False,
    }
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert calls[-1] is None


async def test_filtration_remaining_disabled_keeps_cached_reads(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A time-only context does not force-read, even with the pump running.

    The sensor is disabled by default, so only the default-enabled filtration1
    time entities register a block context. That context must not trigger a
    cache-bypassing force-read.
    """
    calls = _capture_force_read(mock_neopool_client)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Filtration Pump": True,
    }
    await setup_integration(hass, mock_config_entry)
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert calls[-1] is None
