"""Tests for the weheat sensor platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from weheat.abstractions.discovery import HeatPumpDiscovery
from weheat.abstractions.heat_pump import HeatPump

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_weheat_discover: AsyncMock,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(("has_dhw", "nr_of_entities"), [(False, 31), (True, 37)])
async def test_create_entities(
    hass: HomeAssistant,
    mock_weheat_discover: AsyncMock,
    mock_weheat_heat_pump: AsyncMock,
    mock_heat_pump_info: HeatPumpDiscovery.HeatPumpInfo,
    mock_config_entry: MockConfigEntry,
    has_dhw: bool,
    nr_of_entities: int,
) -> None:
    """Test creating entities."""
    mock_heat_pump_info.has_dhw = has_dhw
    mock_weheat_discover.return_value = [mock_heat_pump_info]

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == nr_of_entities


@pytest.mark.parametrize(
    ("cooling_state", "heat_pump_state", "pause_reason", "expected"),
    [
        pytest.param(
            HeatPump.CoolingState.ACTIVE,
            HeatPump.State.COOLING,
            HeatPump.CoolingPauseReason.NONE,
            "active",
            id="in_a_cooling_cycle",
        ),
        pytest.param(
            None,
            HeatPump.State.STANDBY,
            HeatPump.CoolingPauseReason.NONE,
            "waiting",
            id="standby_with_nothing_wrong",
        ),
        pytest.param(
            None,
            HeatPump.State.STANDBY,
            HeatPump.CoolingPauseReason.WATER_TEMPERATURE_BELOW_SETPOINT,
            "paused",
            id="standby_with_a_pause_reason",
        ),
        pytest.param(
            None,
            HeatPump.State.HEATING,
            HeatPump.CoolingPauseReason.WATER_TEMPERATURE_BELOW_SETPOINT,
            "waiting",
            id="heating_ignores_the_pause_reason",
        ),
    ],
)
@pytest.mark.usefixtures("mock_weheat_discover")
async def test_cooling_state(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
    cooling_state: HeatPump.CoolingState | None,
    heat_pump_state: HeatPump.State,
    pause_reason: HeatPump.CoolingPauseReason,
    expected: str,
) -> None:
    """Test the cooling state falls back to why cooling is not running."""
    mock_weheat_heat_pump.cooling_state = cooling_state
    mock_weheat_heat_pump.heat_pump_state = heat_pump_state
    mock_weheat_heat_pump.cooling_pause_reason = pause_reason

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_model_cooling_state").state == expected


@pytest.mark.usefixtures("mock_weheat_discover")
async def test_cooling_state_stopped(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a stop reason is reported when there is no pause reason."""
    mock_weheat_heat_pump.cooling_state = None
    mock_weheat_heat_pump.heat_pump_state = HeatPump.State.STANDBY
    mock_weheat_heat_pump.cooling_pause_reason = HeatPump.CoolingPauseReason.NONE
    mock_weheat_heat_pump.cooling_stop_reason = HeatPump.CoolingStopReason.DTC

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_model_cooling_state").state == "stopped"


def _start_conditions(*unmet: str) -> dict[str, bool]:
    """Build a start condition mapping with the named conditions not met."""
    return {name: name not in unmet for name in HeatPump.COOLING_START_CONDITION_BITS}


@pytest.mark.parametrize(
    ("conditions", "expected"),
    [
        pytest.param(_start_conditions(), "none", id="all_met"),
        pytest.param(
            _start_conditions("outside_air_temperature"),
            "outside_air_temperature",
            id="one_unmet",
        ),
        # the first unmet condition wins, following the order the pump reports them in
        pytest.param(_start_conditions("demand", "dtc"), "dtc", id="several_unmet"),
        pytest.param(None, STATE_UNKNOWN, id="not_decoded"),
    ],
)
@pytest.mark.usefixtures("mock_weheat_discover")
async def test_cooling_blocked_by(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
    conditions: dict[str, bool] | None,
    expected: str,
) -> None:
    """Test the sensor names the condition that is keeping the heat pump from cooling."""
    mock_weheat_heat_pump.cooling_start_conditions = conditions

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_model_cooling_blocked_by").state == expected


@pytest.mark.usefixtures("mock_weheat_discover")
async def test_unrecognised_code_keeps_the_sensor(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a code the library cannot name still creates a sensor, reporting unknown."""
    mock_weheat_heat_pump.cooling_pause_reason = None
    mock_weheat_heat_pump.raw_content = {"cooling_pause_reason": 99}

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("sensor.test_model_cooling_pause_reason").state == STATE_UNKNOWN
    )


@pytest.mark.usefixtures("mock_weheat_discover")
async def test_unreported_field_creates_no_sensor(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a field the heat pump does not report at all creates no sensor."""
    mock_weheat_heat_pump.cooling_pause_reason = None
    mock_weheat_heat_pump.raw_content = {}

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_model_cooling_pause_reason") is None


@pytest.mark.usefixtures("mock_weheat_discover")
async def test_code_becoming_unrecognised_reports_unknown(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a sensor degrades to unknown when a later poll reports an unnamed code."""
    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    mock_weheat_heat_pump.cooling_pause_reason = None
    await mock_config_entry.runtime_data[0].data_coordinator.async_refresh()
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.test_model_cooling_pause_reason").state == STATE_UNKNOWN
    )


@pytest.mark.usefixtures("mock_weheat_discover")
async def test_offline_heat_pump_keeps_its_last_values(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensors keep reporting when the cloud marks the heat pump offline."""
    mock_weheat_heat_pump.is_online = False

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_model_water_inlet_temperature").state == "11"
    assert hass.states.get("sensor.test_model_electricity_used").state == "28689"
