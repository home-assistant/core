"""Tests for the weheat sensor platform."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from weheat.abstractions.discovery import HeatPumpDiscovery
from weheat.abstractions.heat_pump import HeatPump

from homeassistant.components import weheat
from homeassistant.components.weheat.sensor import COOLING_CONDITIONS_NOT_COUNTED
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


@pytest.mark.parametrize(("has_dhw", "nr_of_entities"), [(False, 33), (True, 40)])
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
    ],
)
@pytest.mark.usefixtures("mock_weheat_discover")
async def test_cooling_blocked_by(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
    conditions: dict[str, bool],
    expected: str,
) -> None:
    """Test the sensor names the condition that is keeping the heat pump from cooling."""
    mock_weheat_heat_pump.cooling_start_conditions = conditions

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_model_cooling_blocked_by").state == expected


@pytest.mark.parametrize(
    ("sensor", "attribute", "stale"),
    [
        # the demand condition goes back to unmet as soon as cooling acts on it
        ("cooling_blocked_by", "cooling_start_conditions", _start_conditions("demand")),
        # the pause reason is latched the same way
        (
            "cooling_pause_reason",
            "cooling_pause_reason",
            HeatPump.CoolingPauseReason.WATER_TEMPERATURE_BELOW_SETPOINT,
        ),
        # the stop reason is why the last cycle ended, so it survives into the next
        (
            "cooling_stop_reason",
            "cooling_stop_reason",
            HeatPump.CoolingStopReason.HEAT_PUMP_CONTROL,
        ),
    ],
)
@pytest.mark.usefixtures("mock_weheat_discover")
async def test_stale_cooling_reasons_are_not_reported_while_cooling(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
    sensor: str,
    attribute: str,
    stale: object,
) -> None:
    """Test what held cooling off is not reported once a cycle is running."""
    mock_weheat_heat_pump.heat_pump_state = HeatPump.State.COOLING
    setattr(mock_weheat_heat_pump, attribute, stale)

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(f"sensor.test_model_{sensor}").state == "none"


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        pytest.param(55, "55", id="a_real_target"),
        # a heat pump with DHW control off says so with a zero
        pytest.param(0, STATE_UNKNOWN, id="no_target"),
    ],
)
@pytest.mark.usefixtures("mock_weheat_discover")
async def test_dhw_target_temperature(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
    target: int,
    expected: str,
) -> None:
    """Test a target of zero is reported as no target rather than as freezing."""
    mock_weheat_heat_pump.dhw_target_temperature = target

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_model_dhw_target_temperature").state == expected


@pytest.mark.parametrize(
    ("unmet", "expected"),
    [
        pytest.param((), "9", id="all_met"),
        pytest.param(("demand",), "8", id="one_unmet"),
        # the payload that reported two at once
        pytest.param(("outside_air_temperature", "exponential_backoff"), "7", id="two"),
        pytest.param(
            COOLING_CONDITIONS_NOT_COUNTED, "9", id="settings_are_not_counted"
        ),
    ],
)
@pytest.mark.usefixtures("mock_weheat_discover")
async def test_cooling_conditions_met(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
    unmet: tuple[str, ...],
    expected: str,
) -> None:
    """Test how many start conditions are met is reported alongside the blocker."""
    mock_weheat_heat_pump.cooling_start_conditions = _start_conditions(*unmet)

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_model_cooling_conditions_met").state == expected


@pytest.mark.usefixtures("mock_weheat_discover")
async def test_cooling_conditions_met_is_unknown_while_cooling(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the count is not reported once a cooling cycle is running.

    The demand condition goes back to unmet as soon as the heat pump acts on it,
    so the count would drop by one for the length of the cycle.
    """
    mock_weheat_heat_pump.heat_pump_state = HeatPump.State.COOLING
    mock_weheat_heat_pump.cooling_start_conditions = _start_conditions("demand")

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("sensor.test_model_cooling_conditions_met").state
        == STATE_UNKNOWN
    )


@pytest.mark.usefixtures("mock_weheat_discover")
async def test_unreported_start_conditions_create_no_sensor(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a heat pump that reports no start conditions gets no sensor for them."""
    mock_weheat_heat_pump.cooling_start_conditions = None

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_model_cooling_blocked_by") is None
    assert hass.states.get("sensor.test_model_cooling_conditions_met") is None


@pytest.mark.usefixtures("mock_weheat_discover")
async def test_unrecognised_code_keeps_the_sensor(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a code the library cannot name still creates a sensor, reporting unknown."""
    mock_weheat_heat_pump.cooling_pause_reason = None
    mock_weheat_heat_pump.cooling_pause_reason_code = 99

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
    mock_weheat_heat_pump.cooling_pause_reason_code = None

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
async def test_last_cooling_exists_before_the_first_cooling_cycle(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a heat pump that can cool but has not yet still gets the sensor.

    Entities are only created during setup, so a sensor skipped here would never
    appear once the heat pump does complete a cooling cycle.
    """
    mock_weheat_heat_pump.last_cooling_time = None

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_model_last_cooling").state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("unmet", "expected"),
    [
        # only the wait after a cooling cycle puts a moment on this sensor
        pytest.param(
            ("exponential_backoff",), "2025-06-21T15:30:00+00:00", id="waiting"
        ),
        pytest.param((), STATE_UNKNOWN, id="wait_has_passed"),
        # cooling can be held off for another reason without any wait running
        pytest.param(
            ("outside_air_temperature",), STATE_UNKNOWN, id="blocked_otherwise"
        ),
    ],
)
@pytest.mark.usefixtures("mock_weheat_discover")
async def test_cooling_wait_until(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
    unmet: tuple[str, ...],
    expected: str,
) -> None:
    """Test a moment is reported only while the heat pump is waiting to cool."""
    mock_weheat_heat_pump.cooling_start_conditions = _start_conditions(*unmet)

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_model_cooling_wait_until").state == expected


@pytest.mark.usefixtures("mock_weheat_discover")
async def test_a_heat_pump_without_cooling_gets_no_cooling_sensors(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a heat pump that does not cool gets no cooling sensors at all."""
    mock_weheat_heat_pump.cooling_activity = None
    mock_weheat_heat_pump.last_cooling_time = None
    mock_weheat_heat_pump.cooling_available_from = None
    mock_weheat_heat_pump.cooling_start_conditions = None

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_model_last_cooling") is None
    assert hass.states.get("sensor.test_model_cooling_wait_until") is None


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


def test_the_unit_says_how_many_conditions_are_counted() -> None:
    """Test the total in the sensor unit is the number of conditions counted.

    The unit carries the total so the state reads the way the portal shows it,
    which means a condition added to the library has to be reflected there.
    """
    strings = json.loads((Path(weheat.__file__).parent / "strings.json").read_text())
    counted = len(HeatPump.COOLING_START_CONDITION_BITS) - len(
        COOLING_CONDITIONS_NOT_COUNTED
    )

    assert (
        strings["entity"]["sensor"]["cooling_conditions_met"]["unit_of_measurement"]
        == f"of {counted}"
    )
