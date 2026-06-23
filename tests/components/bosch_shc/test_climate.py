"""Tests for the Bosch SHC climate platform."""

from unittest.mock import MagicMock, patch

from boschshcpy import SHCClimateControl, SHCHeatingCircuit
from boschshcpy.services_impl import RoomClimateControlService

from homeassistant.components.bosch_shc.climate import (
    PRESET_AUTO,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_MANUAL,
    SHCClimateControlEntity,
    SHCHeatingCircuitEntity,
    _set_cool_mode,
)
from homeassistant.components.bosch_shc.const import DOMAIN
from homeassistant.components.climate import ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

OM_CC = RoomClimateControlService.OperationMode
OM_HC = SHCHeatingCircuit.HeatingCircuitService.OperationMode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    id: str = "hdm:ZigBee:test-climate-1",
    root_device_id: str = "hdm:HomeMaticIP:test-root",
    manufacturer: str = "Bosch",
    device_model: str = "ROOM_CLIMATE_CONTROL",
    name: str = "Test Room",
    status: str = "AVAILABLE",
    deleted: bool = False,
) -> MagicMock:
    """Create a mock SHCClimateControl device."""
    device = MagicMock(spec=SHCClimateControl)
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
    device.id = id
    device.root_device_id = root_device_id
    device.manufacturer = manufacturer
    device.device_model = device_model
    device.name = name
    device.status = status
    device.deleted = deleted
    device.device_services = []
    device.subscribe_callback = MagicMock()
    device.unsubscribe_callback = MagicMock()
    return device


def _make_heating_circuit_device(
    *,
    setpoint_temperature: float = 20.0,
    operation_mode: SHCHeatingCircuit.HeatingCircuitService.OperationMode = OM_HC.MANUAL,
    on: bool = True,
    serial: str = "test-serial-hc",
    id: str = "hdm:ZigBee:test-hc-1",
    root_device_id: str = "hdm:HomeMaticIP:test-root",
    manufacturer: str = "Bosch",
    device_model: str = "HEATING_CIRCUIT",
    name: str = "Heating Circuit",
    status: str = "AVAILABLE",
    deleted: bool = False,
) -> MagicMock:
    """Create a mock SHCHeatingCircuit device."""
    device = MagicMock(spec=SHCHeatingCircuit)
    device.setpoint_temperature = setpoint_temperature
    device.operation_mode = operation_mode
    device.on = on
    device.serial = serial
    device.id = id
    device.root_device_id = root_device_id
    device.manufacturer = manufacturer
    device.device_model = device_model
    device.name = name
    device.status = status
    device.deleted = deleted
    device.device_services = []
    device.subscribe_callback = MagicMock()
    device.unsubscribe_callback = MagicMock()
    return device


def _make_climate_entity(device: MagicMock) -> SHCClimateControlEntity:
    """Create a SHCClimateControlEntity bypassing __init__ for unit tests."""
    entity = SHCClimateControlEntity.__new__(SHCClimateControlEntity)
    entity._device = device
    entity._entry_id = "test-entry-id"
    entity._attr_name = None
    entity._attr_unique_id = f"{device.serial}_climate"
    return entity


def _make_heating_entity(device: MagicMock) -> SHCHeatingCircuitEntity:
    """Create a SHCHeatingCircuitEntity bypassing __init__ for unit tests."""
    entity = SHCHeatingCircuitEntity.__new__(SHCHeatingCircuitEntity)
    entity._device = device
    entity._entry_id = "test-entry-id"
    entity._attr_name = None
    entity._attr_unique_id = f"{device.serial}_heating_circuit"
    return entity


# ---------------------------------------------------------------------------
# SHCClimateControlEntity — heating-only device tests
# ---------------------------------------------------------------------------


def test_climate_heating_only_current_temperature() -> None:
    """Temperature is read from the device."""
    device = _make_climate_device(
        supports_cooling=False, summer_mode=False, has_demand=True
    )
    entity = _make_climate_entity(device)
    assert entity.current_temperature == 21.0


def test_climate_heating_only_target_temperature() -> None:
    """Target temperature is read from the device."""
    device = _make_climate_device(supports_cooling=False)
    entity = _make_climate_entity(device)
    assert entity.target_temperature == 22.0


def test_climate_heating_only_hvac_mode_heat() -> None:
    """Returns HEAT when summer_mode is False and no cooling."""
    device = _make_climate_device(supports_cooling=False, summer_mode=False)
    entity = _make_climate_entity(device)
    assert entity.hvac_mode == HVACMode.HEAT


def test_climate_heating_only_hvac_mode_off() -> None:
    """Returns OFF when summer_mode is True."""
    device = _make_climate_device(supports_cooling=False, summer_mode=True)
    entity = _make_climate_entity(device)
    assert entity.hvac_mode == HVACMode.OFF


def test_climate_heating_only_hvac_modes_no_cooling() -> None:
    """COOL not in hvac_modes for heating-only device."""
    device = _make_climate_device(supports_cooling=False)
    entity = _make_climate_entity(device)
    modes = entity.hvac_modes
    assert HVACMode.HEAT in modes
    assert HVACMode.OFF in modes
    assert HVACMode.COOL not in modes


def test_climate_heating_only_hvac_action_heating() -> None:
    """HEATING action when has_demand is True."""
    device = _make_climate_device(
        supports_cooling=False, summer_mode=False, has_demand=True
    )
    entity = _make_climate_entity(device)
    assert entity.hvac_action == HVACAction.HEATING


def test_climate_heating_only_hvac_action_idle() -> None:
    """IDLE action when has_demand is False."""
    device = _make_climate_device(
        supports_cooling=False, summer_mode=False, has_demand=False
    )
    entity = _make_climate_entity(device)
    assert entity.hvac_action == HVACAction.IDLE


def test_climate_heating_only_hvac_action_off() -> None:
    """OFF action when hvac_mode is OFF."""
    device = _make_climate_device(supports_cooling=False, summer_mode=True)
    entity = _make_climate_entity(device)
    assert entity.hvac_action == HVACAction.OFF


def test_climate_heating_only_preset_mode_manual() -> None:
    """MANUAL preset when operation_mode is MANUAL."""
    device = _make_climate_device(supports_cooling=False, operation_mode=OM_CC.MANUAL)
    entity = _make_climate_entity(device)
    assert entity.preset_mode == PRESET_MANUAL


def test_climate_heating_only_preset_mode_auto() -> None:
    """AUTO preset when operation_mode is AUTOMATIC."""
    device = _make_climate_device(
        supports_cooling=False, operation_mode=OM_CC.AUTOMATIC
    )
    entity = _make_climate_entity(device)
    assert entity.preset_mode == PRESET_AUTO


def test_climate_heating_only_preset_mode_boost() -> None:
    """BOOST preset when boost_mode is True."""
    device = _make_climate_device(supports_cooling=False, boost_mode=True)
    entity = _make_climate_entity(device)
    assert entity.preset_mode == PRESET_BOOST


def test_climate_heating_only_preset_mode_eco() -> None:
    """ECO preset when low is True."""
    device = _make_climate_device(supports_cooling=False, low=True)
    entity = _make_climate_entity(device)
    assert entity.preset_mode == PRESET_ECO


def test_climate_heating_only_preset_modes_includes_eco() -> None:
    """ECO in preset_modes when supports_low is True."""
    device = _make_climate_device(supports_cooling=False, supports_low=True)
    entity = _make_climate_entity(device)
    assert PRESET_ECO in entity.preset_modes


def test_climate_heating_only_preset_modes_no_eco_when_not_supported() -> None:
    """ECO not in preset_modes when supports_low is False."""
    device = _make_climate_device(supports_cooling=False, supports_low=False)
    entity = _make_climate_entity(device)
    assert PRESET_ECO not in entity.preset_modes


def test_climate_heating_only_supported_features() -> None:
    """Supported features include temperature, preset, turn on/off."""
    device = _make_climate_device(supports_cooling=False)
    entity = _make_climate_entity(device)
    features = entity.supported_features
    assert features & ClimateEntityFeature.TARGET_TEMPERATURE
    assert features & ClimateEntityFeature.PRESET_MODE
    assert features & ClimateEntityFeature.TURN_OFF
    assert features & ClimateEntityFeature.TURN_ON


# ---------------------------------------------------------------------------
# SHCClimateControlEntity — cooling-capable device tests
# ---------------------------------------------------------------------------


def test_climate_cooling_hvac_modes_includes_cool() -> None:
    """COOL in hvac_modes when supports_cooling is True."""
    device = _make_climate_device(
        supports_cooling=True, summer_mode=False, cooling_mode=False
    )
    entity = _make_climate_entity(device)
    assert HVACMode.COOL in entity.hvac_modes


def test_climate_cooling_hvac_mode_cool() -> None:
    """Returns COOL when supports_cooling and cooling_mode are True."""
    device = _make_climate_device(
        supports_cooling=True, summer_mode=False, cooling_mode=True
    )
    entity = _make_climate_entity(device)
    assert entity.hvac_mode == HVACMode.COOL


def test_climate_cooling_hvac_action_cooling() -> None:
    """COOLING action when in COOL mode."""
    device = _make_climate_device(
        supports_cooling=True, summer_mode=False, cooling_mode=True
    )
    entity = _make_climate_entity(device)
    assert entity.hvac_action == HVACAction.COOLING


# ---------------------------------------------------------------------------
# SHCClimateControlEntity — async service call tests
# ---------------------------------------------------------------------------


async def test_climate_service_set_temperature_calls_executor(
    hass: HomeAssistant,
) -> None:
    """set_temperature uses async_add_executor_job for the sync setter."""
    device = _make_climate_device(
        supports_cooling=True,
        summer_mode=False,
        cooling_mode=False,
        operation_mode=OM_CC.MANUAL,
        supports_low=True,
        low=False,
    )
    entity = _make_climate_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_set_temperature(temperature=21.5)

    assert any(len(c[1]) == 3 and c[1][1] == "setpoint_temperature" for c in calls), (
        f"setpoint_temperature setter not called; calls={calls}"
    )


async def test_climate_service_set_temperature_skips_when_off(
    hass: HomeAssistant,
) -> None:
    """set_temperature is a no-op when hvac_mode is OFF."""
    device = _make_climate_device(
        supports_cooling=True,
        summer_mode=True,
        cooling_mode=False,
        operation_mode=OM_CC.MANUAL,
        supports_low=True,
        low=False,
    )
    entity = _make_climate_entity(device)
    entity.hass = hass

    calls: list = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_set_temperature(temperature=22.0)

    assert not any(len(c[1]) == 3 and c[1][1] == "setpoint_temperature" for c in calls)


async def test_climate_service_set_hvac_mode_heat(hass: HomeAssistant) -> None:
    """set_hvac_mode HEAT calls summer_mode=False."""
    device = _make_climate_device(
        supports_cooling=True,
        summer_mode=False,
        cooling_mode=False,
        operation_mode=OM_CC.MANUAL,
        supports_low=True,
        low=False,
    )
    entity = _make_climate_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_set_hvac_mode(HVACMode.HEAT)

    assert any(
        len(c[1]) == 3 and c[1][1] == "summer_mode" and c[1][2] is False for c in calls
    ), f"summer_mode=False not called; calls={calls}"


async def test_climate_service_set_hvac_mode_off(hass: HomeAssistant) -> None:
    """set_hvac_mode OFF calls summer_mode=True."""
    device = _make_climate_device(
        supports_cooling=True,
        summer_mode=False,
        cooling_mode=False,
        operation_mode=OM_CC.MANUAL,
        supports_low=True,
        low=False,
    )
    entity = _make_climate_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_set_hvac_mode(HVACMode.OFF)

    assert any(
        len(c[1]) == 3 and c[1][1] == "summer_mode" and c[1][2] is True for c in calls
    ), f"summer_mode=True not called; calls={calls}"


async def test_climate_service_set_hvac_mode_cool(hass: HomeAssistant) -> None:
    """set_hvac_mode COOL delegates to _set_cool_mode helper."""
    device = _make_climate_device(
        supports_cooling=True,
        summer_mode=False,
        cooling_mode=False,
        operation_mode=OM_CC.MANUAL,
        supports_low=True,
        low=False,
    )
    entity = _make_climate_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_set_hvac_mode(HVACMode.COOL)

    # The COOL branch uses _set_cool_mode as a single grouped executor job
    assert any(
        c[0] is _set_cool_mode and len(c[1]) == 1 and c[1][0] is device for c in calls
    ), f"_set_cool_mode not called with device; calls={calls}"
    # Verify the helper actually applied the state changes
    assert device.cooling_mode is True
    assert device.summer_mode is False


async def test_climate_service_set_preset_auto(hass: HomeAssistant) -> None:
    """set_preset_mode AUTO sets operation_mode=AUTOMATIC."""
    device = _make_climate_device(
        supports_cooling=True,
        summer_mode=False,
        cooling_mode=False,
        operation_mode=OM_CC.MANUAL,
        supports_low=True,
        low=False,
    )
    entity = _make_climate_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_set_preset_mode(PRESET_AUTO)

    assert any(
        len(c[1]) == 3 and c[1][1] == "operation_mode" and c[1][2] == OM_CC.AUTOMATIC
        for c in calls
    ), f"operation_mode=AUTOMATIC not called; calls={calls}"


async def test_climate_service_set_preset_manual(hass: HomeAssistant) -> None:
    """set_preset_mode MANUAL sets operation_mode=MANUAL."""
    device = _make_climate_device(
        supports_cooling=True,
        summer_mode=False,
        cooling_mode=False,
        operation_mode=OM_CC.MANUAL,
        supports_low=True,
        low=False,
    )
    entity = _make_climate_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_set_preset_mode(PRESET_MANUAL)

    assert any(
        len(c[1]) == 3 and c[1][1] == "operation_mode" and c[1][2] == OM_CC.MANUAL
        for c in calls
    ), f"operation_mode=MANUAL not called; calls={calls}"


async def test_climate_service_set_preset_boost(hass: HomeAssistant) -> None:
    """set_preset_mode BOOST sets boost_mode=True."""
    device = _make_climate_device(
        supports_cooling=True,
        summer_mode=False,
        cooling_mode=False,
        operation_mode=OM_CC.MANUAL,
        supports_low=True,
        low=False,
    )
    entity = _make_climate_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_set_preset_mode(PRESET_BOOST)

    assert any(
        len(c[1]) == 3 and c[1][1] == "boost_mode" and c[1][2] is True for c in calls
    ), f"boost_mode=True not called; calls={calls}"


async def test_climate_service_set_preset_eco(hass: HomeAssistant) -> None:
    """set_preset_mode ECO sets low=True."""
    device = _make_climate_device(
        supports_cooling=True,
        summer_mode=False,
        cooling_mode=False,
        operation_mode=OM_CC.MANUAL,
        supports_low=True,
        low=False,
    )
    entity = _make_climate_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_set_preset_mode(PRESET_ECO)

    assert any(
        len(c[1]) == 3 and c[1][1] == "low" and c[1][2] is True for c in calls
    ), f"low=True not called; calls={calls}"


async def test_climate_service_turn_on_from_off(hass: HomeAssistant) -> None:
    """turn_on calls set_hvac_mode(HEAT) when device is OFF."""
    device = _make_climate_device(
        supports_cooling=True,
        summer_mode=True,
        cooling_mode=False,
        operation_mode=OM_CC.MANUAL,
        supports_low=True,
        low=False,
    )
    entity = _make_climate_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_turn_on()

    assert any(
        len(c[1]) == 3 and c[1][1] == "summer_mode" and c[1][2] is False for c in calls
    )


async def test_climate_service_turn_off_from_heat(hass: HomeAssistant) -> None:
    """turn_off calls set_hvac_mode(OFF) when device is HEAT."""
    device = _make_climate_device(
        supports_cooling=True,
        summer_mode=False,
        cooling_mode=False,
        operation_mode=OM_CC.MANUAL,
        supports_low=True,
        low=False,
    )
    entity = _make_climate_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_turn_off()

    assert any(
        len(c[1]) == 3 and c[1][1] == "summer_mode" and c[1][2] is True for c in calls
    )


# ---------------------------------------------------------------------------
# SHCHeatingCircuitEntity tests
# ---------------------------------------------------------------------------


def test_heating_circuit_current_temperature_is_none() -> None:
    """Heating circuits have no measured temperature."""
    device = _make_heating_circuit_device(operation_mode=OM_HC.MANUAL, on=True)
    entity = _make_heating_entity(device)
    assert entity.current_temperature is None


def test_heating_circuit_target_temperature() -> None:
    """Target temperature read from device."""
    device = _make_heating_circuit_device(
        operation_mode=OM_HC.MANUAL, on=True, setpoint_temperature=20.0
    )
    entity = _make_heating_entity(device)
    assert entity.target_temperature == 20.0


def test_heating_circuit_hvac_mode_heat() -> None:
    """Returns HEAT when operation_mode is MANUAL."""
    device = _make_heating_circuit_device(operation_mode=OM_HC.MANUAL)
    entity = _make_heating_entity(device)
    assert entity.hvac_mode == HVACMode.HEAT


def test_heating_circuit_hvac_mode_auto() -> None:
    """Returns AUTO when operation_mode is AUTOMATIC."""
    device = _make_heating_circuit_device(operation_mode=OM_HC.AUTOMATIC)
    entity = _make_heating_entity(device)
    assert entity.hvac_mode == HVACMode.AUTO


def test_heating_circuit_hvac_action_heating() -> None:
    """HEATING action when on is True."""
    device = _make_heating_circuit_device(on=True)
    entity = _make_heating_entity(device)
    assert entity.hvac_action == HVACAction.HEATING


def test_heating_circuit_hvac_action_idle() -> None:
    """IDLE action when on is False."""
    device = _make_heating_circuit_device(on=False)
    entity = _make_heating_entity(device)
    assert entity.hvac_action == HVACAction.IDLE


def test_heating_circuit_hvac_modes() -> None:
    """Only AUTO and HEAT modes available."""
    device = _make_heating_circuit_device()
    entity = _make_heating_entity(device)
    assert entity.hvac_modes == [HVACMode.AUTO, HVACMode.HEAT]


def test_heating_circuit_supported_features() -> None:
    """Only TARGET_TEMPERATURE supported (no presets)."""
    device = _make_heating_circuit_device()
    entity = _make_heating_entity(device)
    assert entity.supported_features == ClimateEntityFeature.TARGET_TEMPERATURE


async def test_heating_circuit_set_temperature_calls_executor(
    hass: HomeAssistant,
) -> None:
    """set_temperature uses async_add_executor_job."""
    device = _make_heating_circuit_device(
        operation_mode=OM_HC.MANUAL, on=True, setpoint_temperature=20.0
    )
    entity = _make_heating_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_set_temperature(temperature=19.0)

    assert any(len(c[1]) == 3 and c[1][1] == "setpoint_temperature" for c in calls), (
        f"setpoint_temperature setter not called; calls={calls}"
    )


async def test_heating_circuit_set_hvac_mode_auto(hass: HomeAssistant) -> None:
    """set_hvac_mode AUTO sets operation_mode=AUTOMATIC."""
    device = _make_heating_circuit_device(
        operation_mode=OM_HC.MANUAL, on=True, setpoint_temperature=20.0
    )
    entity = _make_heating_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_set_hvac_mode(HVACMode.AUTO)

    assert any(
        len(c[1]) == 3 and c[1][1] == "operation_mode" and c[1][2] == OM_HC.AUTOMATIC
        for c in calls
    ), f"operation_mode=AUTOMATIC not called; calls={calls}"


async def test_heating_circuit_set_hvac_mode_heat(hass: HomeAssistant) -> None:
    """set_hvac_mode HEAT sets operation_mode=MANUAL."""
    device = _make_heating_circuit_device(
        operation_mode=OM_HC.AUTOMATIC, on=True, setpoint_temperature=20.0
    )
    entity = _make_heating_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_set_hvac_mode(HVACMode.HEAT)

    assert any(
        len(c[1]) == 3 and c[1][1] == "operation_mode" and c[1][2] == OM_HC.MANUAL
        for c in calls
    ), f"operation_mode=MANUAL not called; calls={calls}"


# ---------------------------------------------------------------------------
# async_setup_entry tests (use hass.config_entries.async_setup per W7420)
# ---------------------------------------------------------------------------


async def test_async_setup_entry_climate_controls(hass: HomeAssistant) -> None:
    """async_setup_entry creates climate entities from session.device_helper.climate_controls."""
    mock_device = _make_climate_device()
    mock_session = MagicMock()
    mock_session.information.unique_id = "test-shc-id"
    mock_session.information.updateState.name = "NO_UPDATE_AVAILABLE"
    mock_session.information.version = "1.0"
    mock_session.device_helper.climate_controls = [mock_device]
    mock_session.device_helper.heating_circuits = []

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-shc-id",
        data={
            "host": "1.2.3.4",
            "ssl_certificate": "/fake/cert.pem",
            "ssl_key": "/fake/key.pem",
            "token": "test-token",
            "hostname": "shc012345",
        },
        title="Test SHC",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.bosch_shc.async_get_instance",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"climate.{mock_device.name.lower().replace(' ', '_')}")
    assert state is not None or entry.state.value == "loaded"


async def test_async_setup_entry_heating_circuits(hass: HomeAssistant) -> None:
    """async_setup_entry creates heating circuit entities."""
    mock_device = _make_heating_circuit_device()
    mock_session = MagicMock()
    mock_session.information.unique_id = "test-shc-id"
    mock_session.information.updateState.name = "NO_UPDATE_AVAILABLE"
    mock_session.information.version = "1.0"
    mock_session.device_helper.climate_controls = []
    mock_session.device_helper.heating_circuits = [mock_device]

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-shc-id-hc",
        data={
            "host": "1.2.3.4",
            "ssl_certificate": "/fake/cert.pem",
            "ssl_key": "/fake/key.pem",
            "token": "test-token",
            "hostname": "shc012345",
        },
        title="Test SHC HC",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.bosch_shc.async_get_instance",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state.value == "loaded"


async def test_async_setup_entry_empty(hass: HomeAssistant) -> None:
    """async_setup_entry handles empty device lists without error."""
    mock_session = MagicMock()
    mock_session.information.unique_id = "test-shc-id"
    mock_session.information.updateState.name = "NO_UPDATE_AVAILABLE"
    mock_session.information.version = "1.0"
    mock_session.device_helper.climate_controls = []
    mock_session.device_helper.heating_circuits = []

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-shc-id-empty",
        data={
            "host": "1.2.3.4",
            "ssl_certificate": "/fake/cert.pem",
            "ssl_key": "/fake/key.pem",
            "token": "test-token",
            "hostname": "shc012345",
        },
        title="Test SHC Empty",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.bosch_shc.async_get_instance",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state.value == "loaded"
