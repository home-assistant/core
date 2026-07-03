"""Tests for the Bosch SHC climate platform."""

from unittest.mock import MagicMock, create_autospec, patch

from boschshcpy import SHCClimateControl, SHCHeatingCircuit
from boschshcpy.services_impl import RoomClimateControlService
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bosch_shc.climate import (
    PRESET_AUTO,
    PRESET_MANUAL,
    SHCClimateControlEntity,
    SHCHeatingCircuitEntity,
)
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_BOOST,
    PRESET_ECO,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

OM_CC = RoomClimateControlService.OperationMode
OM_HC = SHCHeatingCircuit.HeatingCircuitService.OperationMode


def _make_climate_device(
    *,
    temperature: float = 21.0,
    setpoint_temperature: float = 22.0,
    summer_mode: bool = False,
    cooling_mode: bool = False,
    supports_cooling: bool = False,
    has_demand: bool = True,
    boost_mode: bool = False,
    supports_boost_mode: bool = True,
    low: bool = False,
    supports_low: bool = True,
    operation_mode: RoomClimateControlService.OperationMode = OM_CC.MANUAL,
    serial: str = "test-serial-1",
    name: str = "Test Room",
) -> MagicMock:
    """Create an autospecced SHCClimateControl device."""
    device = create_autospec(SHCClimateControl, instance=True)
    device.temperature = temperature
    device.setpoint_temperature = setpoint_temperature
    device.summer_mode = summer_mode
    device.cooling_mode = cooling_mode
    device.supports_cooling = supports_cooling
    device.has_demand = has_demand
    device.boost_mode = boost_mode
    device.supports_boost_mode = supports_boost_mode
    device.low = low
    device.supports_low = supports_low
    device.operation_mode = operation_mode
    device.serial = serial
    device.id = f"{serial}-id"
    device.root_device_id = "shc-test-uid"
    device.manufacturer = "Bosch"
    device.device_model = "ROOM_CLIMATE_CONTROL"
    device.name = name
    device.status = "AVAILABLE"
    device.deleted = False
    device.device_services = []
    return device


def _make_heating_circuit_device(
    *,
    setpoint_temperature: float = 20.0,
    operation_mode: SHCHeatingCircuit.HeatingCircuitService.OperationMode = OM_HC.MANUAL,
    on: bool = True,
    serial: str = "test-serial-hc",
    name: str = "Heating Circuit",
) -> MagicMock:
    """Create an autospecced SHCHeatingCircuit device."""
    device = create_autospec(SHCHeatingCircuit, instance=True)
    device.setpoint_temperature = setpoint_temperature
    device.operation_mode = operation_mode
    device.on = on
    device.serial = serial
    device.id = f"{serial}-id"
    device.root_device_id = "shc-test-uid"
    device.manufacturer = "Bosch"
    device.device_model = "HEATING_CIRCUIT"
    device.name = name
    device.status = "AVAILABLE"
    device.deleted = False
    device.device_services = []
    return device


async def _setup_climate_platform(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Set up the bosch_shc config entry with only the climate platform loaded."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch("homeassistant.components.bosch_shc.async_get_instance"),
        patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.CLIMATE]),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


# The computed-property tests below construct the entity directly (no hass
# setup) since they only exercise pure property logic with no I/O.
def test_climate_current_and_target_temperature() -> None:
    """Temperatures are read straight from the device."""
    device = _make_climate_device(temperature=21.0, setpoint_temperature=22.0)
    entity = SHCClimateControlEntity(
        device=device, parent_id="shc-test-uid", entry_id="e"
    )
    assert entity.current_temperature == 21.0
    assert entity.target_temperature == 22.0


@pytest.mark.parametrize(
    ("supports_cooling", "summer_mode", "cooling_mode", "expected"),
    [
        pytest.param(False, False, False, HVACMode.HEAT, id="heating_only_heat"),
        pytest.param(False, True, False, HVACMode.OFF, id="heating_only_off"),
        pytest.param(True, False, True, HVACMode.COOL, id="cooling_capable_cool"),
        pytest.param(
            True, True, True, HVACMode.OFF, id="summer_mode_wins_over_cooling"
        ),
    ],
)
def test_climate_hvac_mode(
    supports_cooling: bool,
    summer_mode: bool,
    cooling_mode: bool,
    expected: HVACMode,
) -> None:
    """hvac_mode reflects the direction axis (summer_mode, then cooling_mode)."""
    device = _make_climate_device(
        supports_cooling=supports_cooling,
        summer_mode=summer_mode,
        cooling_mode=cooling_mode,
    )
    entity = SHCClimateControlEntity(
        device=device, parent_id="shc-test-uid", entry_id="e"
    )
    assert entity.hvac_mode == expected


@pytest.mark.parametrize(
    ("supports_cooling", "expected_modes"),
    [
        pytest.param(False, {HVACMode.HEAT, HVACMode.OFF}, id="heating_only"),
        pytest.param(
            True, {HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF}, id="cooling_capable"
        ),
    ],
)
def test_climate_hvac_modes(
    supports_cooling: bool, expected_modes: set[HVACMode]
) -> None:
    """COOL only appears in hvac_modes when the device supports it."""
    device = _make_climate_device(supports_cooling=supports_cooling)
    entity = SHCClimateControlEntity(
        device=device, parent_id="shc-test-uid", entry_id="e"
    )
    assert set(entity.hvac_modes) == expected_modes


@pytest.mark.parametrize(
    ("summer_mode", "cooling_mode", "supports_cooling", "has_demand", "expected"),
    [
        pytest.param(True, False, False, True, HVACAction.OFF, id="off"),
        pytest.param(False, True, True, True, HVACAction.COOLING, id="cooling"),
        pytest.param(False, False, False, True, HVACAction.HEATING, id="heating"),
        pytest.param(False, False, False, False, HVACAction.IDLE, id="idle"),
    ],
)
def test_climate_hvac_action(
    summer_mode: bool,
    cooling_mode: bool,
    supports_cooling: bool,
    has_demand: bool,
    expected: HVACAction,
) -> None:
    """hvac_action follows OFF > COOLING > HEATING/IDLE precedence."""
    device = _make_climate_device(
        summer_mode=summer_mode,
        cooling_mode=cooling_mode,
        supports_cooling=supports_cooling,
        has_demand=has_demand,
    )
    entity = SHCClimateControlEntity(
        device=device, parent_id="shc-test-uid", entry_id="e"
    )
    assert entity.hvac_action == expected


@pytest.mark.parametrize(
    ("boost_mode", "low", "operation_mode", "expected"),
    [
        pytest.param(True, False, OM_CC.MANUAL, PRESET_BOOST, id="boost_wins"),
        pytest.param(False, True, OM_CC.MANUAL, PRESET_ECO, id="eco"),
        pytest.param(False, False, OM_CC.AUTOMATIC, PRESET_AUTO, id="auto"),
        pytest.param(False, False, OM_CC.MANUAL, PRESET_MANUAL, id="manual"),
    ],
)
def test_climate_preset_mode(
    boost_mode: bool,
    low: bool,
    operation_mode: RoomClimateControlService.OperationMode,
    expected: str,
) -> None:
    """preset_mode follows boost > eco > auto/manual precedence."""
    device = _make_climate_device(
        boost_mode=boost_mode, low=low, operation_mode=operation_mode
    )
    entity = SHCClimateControlEntity(
        device=device, parent_id="shc-test-uid", entry_id="e"
    )
    assert entity.preset_mode == expected


@pytest.mark.parametrize(
    ("supports_boost_mode", "supports_low", "expected"),
    [
        pytest.param(
            True,
            True,
            {PRESET_AUTO, PRESET_MANUAL, PRESET_BOOST, PRESET_ECO},
            id="all_supported",
        ),
        pytest.param(False, False, {PRESET_AUTO, PRESET_MANUAL}, id="none_supported"),
    ],
)
def test_climate_preset_modes(
    supports_boost_mode: bool, supports_low: bool, expected: set[str]
) -> None:
    """preset_modes only lists boost/eco when the device supports them."""
    device = _make_climate_device(
        supports_boost_mode=supports_boost_mode, supports_low=supports_low
    )
    entity = SHCClimateControlEntity(
        device=device, parent_id="shc-test-uid", entry_id="e"
    )
    assert set(entity.preset_modes) == expected


def test_climate_supported_features() -> None:
    """Supported features include temperature, preset, turn on/off."""
    device = _make_climate_device()
    entity = SHCClimateControlEntity(
        device=device, parent_id="shc-test-uid", entry_id="e"
    )
    features = entity.supported_features
    assert features & ClimateEntityFeature.TARGET_TEMPERATURE
    assert features & ClimateEntityFeature.PRESET_MODE
    assert features & ClimateEntityFeature.TURN_OFF
    assert features & ClimateEntityFeature.TURN_ON


def test_heating_circuit_current_temperature_is_none() -> None:
    """Heating circuits have no measured temperature."""
    device = _make_heating_circuit_device()
    entity = SHCHeatingCircuitEntity(
        device=device, parent_id="shc-test-uid", entry_id="e"
    )
    assert entity.current_temperature is None


def test_heating_circuit_target_temperature() -> None:
    """Target temperature is read from the device."""
    device = _make_heating_circuit_device(setpoint_temperature=20.0)
    entity = SHCHeatingCircuitEntity(
        device=device, parent_id="shc-test-uid", entry_id="e"
    )
    assert entity.target_temperature == 20.0


@pytest.mark.parametrize(
    ("operation_mode", "expected"),
    [
        pytest.param(OM_HC.MANUAL, HVACMode.HEAT, id="manual_is_heat"),
        pytest.param(OM_HC.AUTOMATIC, HVACMode.AUTO, id="automatic_is_auto"),
    ],
)
def test_heating_circuit_hvac_mode(
    operation_mode: SHCHeatingCircuit.HeatingCircuitService.OperationMode,
    expected: HVACMode,
) -> None:
    """hvac_mode is derived from the operation mode."""
    device = _make_heating_circuit_device(operation_mode=operation_mode)
    entity = SHCHeatingCircuitEntity(
        device=device, parent_id="shc-test-uid", entry_id="e"
    )
    assert entity.hvac_mode == expected


@pytest.mark.parametrize(
    ("on", "expected"),
    [
        pytest.param(True, HVACAction.HEATING, id="on_is_heating"),
        pytest.param(False, HVACAction.IDLE, id="off_is_idle"),
    ],
)
def test_heating_circuit_hvac_action(on: bool, expected: HVACAction) -> None:
    """hvac_action reflects whether the circuit currently has demand."""
    device = _make_heating_circuit_device(on=on)
    entity = SHCHeatingCircuitEntity(
        device=device, parent_id="shc-test-uid", entry_id="e"
    )
    assert entity.hvac_action == expected


def test_heating_circuit_hvac_modes_and_features() -> None:
    """Only AUTO/HEAT and TARGET_TEMPERATURE (no presets) are exposed."""
    device = _make_heating_circuit_device()
    entity = SHCHeatingCircuitEntity(
        device=device, parent_id="shc-test-uid", entry_id="e"
    )
    assert entity.hvac_modes == [HVACMode.AUTO, HVACMode.HEAT]
    assert entity.supported_features == ClimateEntityFeature.TARGET_TEMPERATURE


async def test_climate_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """Both climate-control and heating-circuit entities are created."""
    mock_session.device_helper.climate_controls = [
        _make_climate_device(supports_cooling=True, serial="cc-serial")
    ]
    mock_session.device_helper.heating_circuits = [
        _make_heating_circuit_device(serial="hc-serial")
    ]

    await _setup_climate_platform(hass, mock_config_entry, mock_session)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_no_climate_entities_when_no_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """No climate entities are created when both device lists are empty."""
    await _setup_climate_platform(hass, mock_config_entry, mock_session)

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


async def test_climate_control_set_temperature(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Setting a temperature within range writes setpoint_temperature."""
    device = _make_climate_device(
        supports_cooling=True, summer_mode=False, operation_mode=OM_CC.MANUAL
    )
    mock_session.device_helper.climate_controls = [device]
    await _setup_climate_platform(hass, mock_config_entry, mock_session)
    (entity_id,) = hass.states.async_entity_ids(CLIMATE_DOMAIN)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 21.5},
        blocking=True,
    )

    assert device.setpoint_temperature == 21.5


async def test_climate_control_set_temperature_drops_automatic_to_manual(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """A bare temperature write while AUTOMATIC switches to MANUAL first."""
    device = _make_climate_device(
        supports_cooling=True, summer_mode=False, operation_mode=OM_CC.AUTOMATIC
    )
    mock_session.device_helper.climate_controls = [device]
    await _setup_climate_platform(hass, mock_config_entry, mock_session)
    (entity_id,) = hass.states.async_entity_ids(CLIMATE_DOMAIN)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 22.0},
        blocking=True,
    )

    assert device.operation_mode == OM_CC.MANUAL
    assert device.setpoint_temperature == 22.0


async def test_climate_control_set_temperature_skips_when_off(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Setting a temperature is a no-op while hvac_mode is OFF."""
    device = _make_climate_device(
        supports_cooling=True, summer_mode=True, operation_mode=OM_CC.MANUAL
    )
    mock_session.device_helper.climate_controls = [device]
    await _setup_climate_platform(hass, mock_config_entry, mock_session)
    (entity_id,) = hass.states.async_entity_ids(CLIMATE_DOMAIN)
    original_setpoint = device.setpoint_temperature

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 22.0},
        blocking=True,
    )

    assert device.setpoint_temperature == original_setpoint


@pytest.mark.parametrize(
    ("hvac_mode", "expected_summer_mode", "expected_cooling_mode"),
    [
        pytest.param(HVACMode.HEAT, False, False, id="heat"),
        pytest.param(HVACMode.OFF, True, False, id="off"),
        pytest.param(HVACMode.COOL, False, True, id="cool"),
    ],
)
async def test_climate_control_set_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    hvac_mode: HVACMode,
    expected_summer_mode: bool,
    expected_cooling_mode: bool,
) -> None:
    """set_hvac_mode writes the direction-axis fields for each target mode."""
    device = _make_climate_device(
        supports_cooling=True, summer_mode=False, cooling_mode=False
    )
    mock_session.device_helper.climate_controls = [device]
    await _setup_climate_platform(hass, mock_config_entry, mock_session)
    (entity_id,) = hass.states.async_entity_ids(CLIMATE_DOMAIN)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    assert device.summer_mode is expected_summer_mode
    assert device.cooling_mode is expected_cooling_mode


@pytest.mark.parametrize(
    ("preset_mode", "expect_boost", "expect_low", "expect_operation_mode"),
    [
        # boost/eco don't touch operation_mode, so it stays at the device's
        # starting value (MANUAL, set below).
        pytest.param(PRESET_BOOST, True, False, OM_CC.MANUAL, id="boost"),
        pytest.param(PRESET_ECO, False, True, OM_CC.MANUAL, id="eco"),
        pytest.param(PRESET_AUTO, False, False, OM_CC.AUTOMATIC, id="auto"),
        pytest.param(PRESET_MANUAL, False, False, OM_CC.MANUAL, id="manual"),
    ],
)
async def test_climate_control_set_preset_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    preset_mode: str,
    expect_boost: bool,
    expect_low: bool,
    expect_operation_mode: RoomClimateControlService.OperationMode,
) -> None:
    """set_preset_mode writes the regulation-axis fields for each preset."""
    device = _make_climate_device(
        supports_cooling=True,
        boost_mode=False,
        low=False,
        operation_mode=OM_CC.MANUAL,
    )
    mock_session.device_helper.climate_controls = [device]
    await _setup_climate_platform(hass, mock_config_entry, mock_session)
    (entity_id,) = hass.states.async_entity_ids(CLIMATE_DOMAIN)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, "preset_mode": preset_mode},
        blocking=True,
    )

    assert device.boost_mode is expect_boost
    assert device.low is expect_low
    assert device.operation_mode == expect_operation_mode


async def test_climate_control_turn_on_from_off(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """turn_on switches an OFF device to HEAT."""
    device = _make_climate_device(supports_cooling=True, summer_mode=True)
    mock_session.device_helper.climate_controls = [device]
    await _setup_climate_platform(hass, mock_config_entry, mock_session)
    (entity_id,) = hass.states.async_entity_ids(CLIMATE_DOMAIN)

    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert device.summer_mode is False


async def test_climate_control_turn_off_from_heat(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """turn_off switches a HEAT device to OFF."""
    device = _make_climate_device(supports_cooling=True, summer_mode=False)
    mock_session.device_helper.climate_controls = [device]
    await _setup_climate_platform(hass, mock_config_entry, mock_session)
    (entity_id,) = hass.states.async_entity_ids(CLIMATE_DOMAIN)

    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert device.summer_mode is True


async def test_heating_circuit_set_temperature(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Setting a temperature writes setpoint_temperature."""
    device = _make_heating_circuit_device(setpoint_temperature=20.0)
    mock_session.device_helper.heating_circuits = [device]
    await _setup_climate_platform(hass, mock_config_entry, mock_session)
    (entity_id,) = hass.states.async_entity_ids(CLIMATE_DOMAIN)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 19.0},
        blocking=True,
    )

    assert device.setpoint_temperature == 19.0


@pytest.mark.parametrize(
    ("hvac_mode", "starting_operation_mode", "expected_operation_mode"),
    [
        pytest.param(HVACMode.AUTO, OM_HC.MANUAL, OM_HC.AUTOMATIC, id="to_auto"),
        pytest.param(HVACMode.HEAT, OM_HC.AUTOMATIC, OM_HC.MANUAL, id="to_heat"),
    ],
)
async def test_heating_circuit_set_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    hvac_mode: HVACMode,
    starting_operation_mode: SHCHeatingCircuit.HeatingCircuitService.OperationMode,
    expected_operation_mode: SHCHeatingCircuit.HeatingCircuitService.OperationMode,
) -> None:
    """set_hvac_mode maps AUTO/HEAT onto the AUTOMATIC/MANUAL operation mode."""
    device = _make_heating_circuit_device(operation_mode=starting_operation_mode)
    mock_session.device_helper.heating_circuits = [device]
    await _setup_climate_platform(hass, mock_config_entry, mock_session)
    (entity_id,) = hass.states.async_entity_ids(CLIMATE_DOMAIN)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    assert device.operation_mode == expected_operation_mode
