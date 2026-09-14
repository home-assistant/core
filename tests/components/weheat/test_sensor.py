"""Tests for the weheat sensor platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from weheat.abstractions.discovery import HeatPumpDiscovery
from weheat.abstractions.heat_pump import HeatPump

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.weheat.sensor import COOLING_CONDITIONS_NOT_COUNTED
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN, Platform
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


@pytest.mark.parametrize(("has_dhw", "nr_of_entities"), [(False, 32), (True, 39)])
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
    ("target", "expected"),
    [
        pytest.param(55, "55", id="a_target_it_aims_for"),
        # DHW control off reports a target of zero, which is no target at all
        pytest.param(0, STATE_UNKNOWN, id="dhw_control_off"),
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
    """Test the DHW target is only reported when the heat pump has one."""
    mock_weheat_heat_pump.dhw_target_temperature = target

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_model_dhw_target_temperature").state == expected


@pytest.mark.usefixtures("mock_weheat_discover")
async def test_an_unknown_dhw_control_method_keeps_the_sensor(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a control method this library cannot name still gets a sensor."""
    mock_weheat_heat_pump.dhw_control_method = None
    mock_weheat_heat_pump.dhw_control_method_code = 99

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("sensor.test_model_dhw_control_method").state == STATE_UNKNOWN
    )


# The cooling sensors a heat pump that does not cool must not get. The cooling
# energy counters are not among them: those are reported either way, at zero.
COOLING_SENSORS = {
    "sensor.test_model_cooling_state",
    "sensor.test_model_cooling_blocked_by",
    "sensor.test_model_cooling_conditions_met",
    "sensor.test_model_cooling_wait_until",
    "sensor.test_model_last_cooling",
    "sensor.test_model_cooling_pause_reason",
    "sensor.test_model_cooling_stop_reason",
}


CONDITIONS_COUNTED = len(HeatPump.COOLING_START_CONDITION_BITS) - len(
    COOLING_CONDITIONS_NOT_COUNTED
)


def _start_conditions(*unmet: str) -> dict[str, bool]:
    """Build a start condition mapping with the named conditions not met."""
    return {name: name not in unmet for name in HeatPump.COOLING_START_CONDITION_BITS}


@pytest.mark.parametrize(
    ("unmet", "expected"),
    [
        pytest.param((), "9", id="all_met"),
        pytest.param(("demand",), "8", id="one_unmet"),
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
    """Test how many start conditions are met is counted as the portal counts."""
    mock_weheat_heat_pump.cooling_start_conditions = _start_conditions(*unmet)

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.test_model_cooling_conditions_met")

    assert state.state == expected
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == f"of {CONDITIONS_COUNTED}"


@pytest.mark.parametrize(
    ("cooling_state", "heat_pump_state"),
    [
        pytest.param(HeatPump.CoolingState.ACTIVE, HeatPump.State.COOLING, id="active"),
        pytest.param(HeatPump.CoolingState.IDLE, HeatPump.State.COOLING, id="idle"),
        # the heat pump reports the water check as a state of its own, so the
        # overall state is not cooling while the cooling cycle still is
        pytest.param(
            HeatPump.CoolingState.WATER_CHECK,
            HeatPump.State.WATER_CHECK,
            id="water_check",
        ),
    ],
)
@pytest.mark.usefixtures("mock_weheat_discover")
async def test_cooling_conditions_met_is_unknown_while_cooling(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
    cooling_state: HeatPump.CoolingState,
    heat_pump_state: HeatPump.State,
) -> None:
    """Test the count is not reported once a cooling cycle is running."""
    mock_weheat_heat_pump.heat_pump_state = heat_pump_state
    mock_weheat_heat_pump.cooling_state = cooling_state
    mock_weheat_heat_pump.cooling_start_conditions = _start_conditions("demand")

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("sensor.test_model_cooling_conditions_met").state
        == STATE_UNKNOWN
    )


@pytest.mark.parametrize(
    ("sensor", "attribute", "stale"),
    [
        pytest.param(
            "cooling_pause_reason",
            "cooling_pause_reason",
            HeatPump.CoolingPauseReason.ROOM_TEMPERATURE_TOO_LOW,
            id="pause_reason",
        ),
        pytest.param(
            "cooling_stop_reason",
            "cooling_stop_reason",
            HeatPump.CoolingStopReason.HEAT_PUMP_CONTROL,
            id="stop_reason",
        ),
        pytest.param(
            "cooling_blocked_by",
            "cooling_start_conditions",
            dict.fromkeys(HeatPump.COOLING_START_CONDITION_BITS, False),
            id="blocked_by",
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
    mock_weheat_heat_pump.cooling_state = HeatPump.CoolingState.ACTIVE
    setattr(mock_weheat_heat_pump, attribute, stale)

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(f"sensor.test_model_{sensor}").state == "none"


@pytest.mark.usefixtures("mock_weheat_discover")
async def test_a_heat_pump_without_cooling_gets_no_cooling_sensors(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a heat pump that does not cool gets no cooling sensors at all."""
    mock_weheat_heat_pump.cooling_activity = None

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert [
        entity_id
        for entity_id in hass.states.async_entity_ids(SENSOR_DOMAIN)
        if entity_id in COOLING_SENSORS
    ] == []


@pytest.mark.usefixtures("mock_weheat_discover")
async def test_cooling_without_start_conditions(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a cooling heat pump that reports no start conditions keeps its sensors."""
    mock_weheat_heat_pump.cooling_start_conditions = None

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("sensor.test_model_cooling_blocked_by").state == STATE_UNKNOWN
    )
    assert (
        hass.states.get("sensor.test_model_cooling_conditions_met").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get("sensor.test_model_cooling_wait_until").state == STATE_UNKNOWN
    )
    assert (
        hass.states.get("sensor.test_model_cooling_pause_reason").state != STATE_UNKNOWN
    )
