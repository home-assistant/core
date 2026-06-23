"""Tests for the Bosch SHC climate platform."""

from unittest.mock import AsyncMock, MagicMock

from boschshcpy import SHCClimateControl, SHCHeatingCircuit
import pytest

from homeassistant.components.bosch_shc.const import DOMAIN, OPT_EXCLUDED_DEVICES
from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN as CLIMATE_DOMAIN,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import make_device, setup_integration

from tests.common import MockConfigEntry

# Shorthand aliases for the Bosch enums used in tests
_CC_OP = SHCClimateControl.RoomClimateControlService.OperationMode
_HC_OP = SHCHeatingCircuit.HeatingCircuitService.OperationMode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_climate_device(
    device_id: str = "climate-1",
    name: str = "Living Room",
    room_id: str = "room-1",
    temperature: float = 21.5,
    setpoint_temperature: float = 22.0,
    summer_mode: bool = False,
    cooling_mode: bool = False,
    supports_cooling: bool = False,
    has_demand: bool = True,
    operation_mode=None,
    boost_mode: bool = False,
    supports_boost_mode: bool = True,
    low: bool = False,
    supports_low: bool = True,
) -> MagicMock:
    """Build a mock SHCClimateControl device."""
    if operation_mode is None:
        operation_mode = _CC_OP.AUTOMATIC

    device = make_device(
        device_id=device_id,
        name=name,
        status="AVAILABLE",
        temperature=temperature,
        setpoint_temperature=setpoint_temperature,
        summer_mode=summer_mode,
        cooling_mode=cooling_mode,
        supports_cooling=supports_cooling,
        has_demand=has_demand,
        operation_mode=operation_mode,
        boost_mode=boost_mode,
        supports_boost_mode=supports_boost_mode,
        low=low,
        supports_low=supports_low,
    )
    device.room_id = room_id
    # Async setters — all return None by default.
    device.async_set_setpoint_temperature = AsyncMock()
    device.async_set_operation_mode = AsyncMock()
    device.async_set_summer_mode = AsyncMock()
    device.async_set_cooling_mode = AsyncMock()
    device.async_set_boost_mode = AsyncMock()
    device.async_set_low = AsyncMock()
    return device


def _make_heating_circuit(
    device_id: str = "hc-1",
    name: str = "Heating Circuit 1",
    setpoint_temperature: float = 20.0,
    operation_mode=None,
    on: bool = True,
) -> MagicMock:
    """Build a mock SHCHeatingCircuit device."""
    if operation_mode is None:
        operation_mode = _HC_OP.AUTOMATIC

    device = make_device(
        device_id=device_id,
        name=name,
        status="AVAILABLE",
        setpoint_temperature=setpoint_temperature,
        operation_mode=operation_mode,
        on=on,
    )
    device.async_set_setpoint_temperature = AsyncMock()
    device.async_set_operation_mode = AsyncMock()
    return device


def _make_config_entry_with_options(options: dict) -> MockConfigEntry:
    """Return a config entry pre-loaded with the given options."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="shc012345",
        unique_id="test-mac",
        entry_id="01JE69BM3MA48YE6RH05A4MDKQ",
        data={
            "host": "1.1.1.1",
            "ssl_certificate": "/etc/bosch_shc/test-cert.pem",
            "ssl_key": "/etc/bosch_shc/test-key.pem",
            "token": "abc:test-mac",
            "hostname": "test-mac",
        },
        options=options,
    )


def _inject_climate(mock_session: MagicMock, device: MagicMock, room_name: str = "Living Room") -> None:
    """Add a climate_control device and a matching room mock to the session."""
    room = MagicMock()
    room.name = room_name
    mock_session.room = MagicMock(return_value=room)
    mock_session.device_helper.climate_controls = [device]


# ---------------------------------------------------------------------------
# ClimateControl — state / attribute tests
# ---------------------------------------------------------------------------


async def test_climate_control_heating_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Heating-only device (no cooling) has hvac_mode=heat and hvac_modes=[heat, off]."""
    device = _make_climate_device(
        device_id="cc-heat",
        name="Office",
        summer_mode=False,
        supports_cooling=False,
        has_demand=True,
        operation_mode=_CC_OP.AUTOMATIC,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Office")

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.office")
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    assert HVACMode.HEAT in state.attributes[ATTR_HVAC_MODES]
    assert HVACMode.OFF in state.attributes[ATTR_HVAC_MODES]
    assert HVACMode.COOL not in state.attributes[ATTR_HVAC_MODES]
    assert state.attributes[ATTR_TEMPERATURE] == 22.0
    assert state.attributes["current_temperature"] == 21.5


async def test_climate_control_off_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """summer_mode=True maps to HVACMode.OFF; action is HVACAction.OFF."""
    device = _make_climate_device(
        device_id="cc-off",
        name="Bedroom",
        summer_mode=True,
        supports_cooling=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Bedroom")

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.bedroom")
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF


async def test_climate_control_cool_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Cooling-capable device with cooling_mode=True has hvac_mode=cool + action=cooling."""
    device = _make_climate_device(
        device_id="cc-cool",
        name="Hall",
        summer_mode=False,
        supports_cooling=True,
        cooling_mode=True,
        has_demand=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Hall")

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.hall")
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING
    assert HVACMode.COOL in state.attributes[ATTR_HVAC_MODES]
    assert HVACMode.HEAT in state.attributes[ATTR_HVAC_MODES]
    assert HVACMode.OFF in state.attributes[ATTR_HVAC_MODES]


async def test_climate_control_supports_cooling_heat_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Cooling-capable device NOT in cooling mode = HEAT; COOL still in hvac_modes."""
    device = _make_climate_device(
        device_id="cc-cool-heat",
        name="Conservatory",
        summer_mode=False,
        supports_cooling=True,
        cooling_mode=False,
        has_demand=True,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Conservatory")

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.conservatory")
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert HVACMode.COOL in state.attributes[ATTR_HVAC_MODES]


async def test_climate_control_idle_action(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """has_demand=False in HEAT mode yields HVACAction.IDLE."""
    device = _make_climate_device(
        device_id="cc-idle",
        name="Garage",
        summer_mode=False,
        supports_cooling=False,
        has_demand=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Garage")

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.garage")
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_climate_control_preset_auto(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """operation_mode=AUTOMATIC + no overrides → preset_mode='auto'."""
    device = _make_climate_device(
        device_id="cc-auto",
        name="Kitchen",
        operation_mode=_CC_OP.AUTOMATIC,
        boost_mode=False,
        low=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Kitchen")

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.kitchen")
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "auto"
    assert "auto" in state.attributes[ATTR_PRESET_MODES]
    assert "manual" in state.attributes[ATTR_PRESET_MODES]
    assert "boost" in state.attributes[ATTR_PRESET_MODES]
    assert "eco" in state.attributes[ATTR_PRESET_MODES]


async def test_climate_control_preset_manual(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """operation_mode=MANUAL + no overrides → preset_mode='manual'."""
    device = _make_climate_device(
        device_id="cc-manual",
        name="Study",
        operation_mode=_CC_OP.MANUAL,
        boost_mode=False,
        low=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Study")

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.study")
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "manual"


async def test_climate_control_preset_boost(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """boost_mode=True → preset_mode='boost' (takes precedence over operation_mode)."""
    device = _make_climate_device(
        device_id="cc-boost",
        name="Attic",
        boost_mode=True,
        supports_boost_mode=True,
        low=False,
        operation_mode=_CC_OP.MANUAL,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Attic")

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.attic")
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "boost"


async def test_climate_control_preset_eco(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """low=True (and supports_low=True) → preset_mode='eco'."""
    device = _make_climate_device(
        device_id="cc-eco",
        name="Basement",
        boost_mode=False,
        supports_boost_mode=True,
        low=True,
        supports_low=True,
        operation_mode=_CC_OP.MANUAL,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Basement")

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.basement")
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "eco"


async def test_climate_control_no_eco_when_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Device without supports_low should NOT list 'eco' in preset_modes."""
    device = _make_climate_device(
        device_id="cc-noeco",
        name="Utility",
        supports_low=False,
        supports_boost_mode=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Utility")

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.utility")
    assert state is not None
    assert "eco" not in state.attributes[ATTR_PRESET_MODES]
    assert "boost" not in state.attributes[ATTR_PRESET_MODES]


# ---------------------------------------------------------------------------
# ClimateControl — service calls
# ---------------------------------------------------------------------------


async def test_set_temperature_in_auto_switches_to_manual(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_temperature without hvac_mode switches AUTOMATIC → MANUAL first."""
    device = _make_climate_device(
        device_id="cc-settemp",
        name="Dining",
        operation_mode=_CC_OP.AUTOMATIC,
        summer_mode=False,
        boost_mode=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Dining")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {"entity_id": "climate.dining", ATTR_TEMPERATURE: 21.0},
        blocking=True,
    )

    # Must have switched to MANUAL before setting the setpoint
    device.async_set_operation_mode.assert_awaited_once_with(_CC_OP.MANUAL)
    device.async_set_setpoint_temperature.assert_awaited_once_with(21.0)


async def test_set_temperature_in_manual_no_mode_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_temperature while already MANUAL must NOT call async_set_operation_mode."""
    device = _make_climate_device(
        device_id="cc-settemp-m",
        name="Porch",
        operation_mode=_CC_OP.MANUAL,
        summer_mode=False,
        boost_mode=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Porch")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {"entity_id": "climate.porch", ATTR_TEMPERATURE: 19.5},
        blocking=True,
    )

    device.async_set_operation_mode.assert_not_awaited()
    device.async_set_setpoint_temperature.assert_awaited_once_with(19.5)


async def test_set_temperature_rounds_to_half(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Setpoint is rounded to nearest 0.5 step before writing."""
    device = _make_climate_device(
        device_id="cc-round",
        name="Laundry",
        operation_mode=_CC_OP.MANUAL,
        summer_mode=False,
        boost_mode=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Laundry")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {"entity_id": "climate.laundry", ATTR_TEMPERATURE: 20.3},
        blocking=True,
    )

    # 20.3 rounds to 20.5 (nearest 0.5)
    device.async_set_setpoint_temperature.assert_awaited_once_with(20.5)


async def test_set_temperature_skipped_when_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_temperature is silently ignored when device is in OFF (summer) mode."""
    device = _make_climate_device(
        device_id="cc-off-temp",
        name="Patio",
        summer_mode=True,
        boost_mode=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Patio")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {"entity_id": "climate.patio", ATTR_TEMPERATURE: 20.0},
        blocking=True,
    )

    device.async_set_setpoint_temperature.assert_not_awaited()


async def test_set_temperature_out_of_range_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_temperature outside [5, 30] is rejected by HA climate platform validation."""
    device = _make_climate_device(
        device_id="cc-oob",
        name="Sauna",
        operation_mode=_CC_OP.MANUAL,
        summer_mode=False,
        boost_mode=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Sauna")

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            "set_temperature",
            {"entity_id": "climate.sauna", ATTR_TEMPERATURE: 99.0},
            blocking=True,
        )

    device.async_set_setpoint_temperature.assert_not_awaited()


async def test_set_hvac_mode_heat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_hvac_mode(heat) calls async_set_summer_mode(False) [and async_set_cooling_mode(False) if supports_cooling]."""
    device = _make_climate_device(
        device_id="cc-hvac-heat",
        name="Sauna Room",
        summer_mode=True,
        supports_cooling=False,
        boost_mode=False,
        low=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Sauna Room")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {"entity_id": "climate.sauna_room", ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    device.async_set_summer_mode.assert_awaited_once_with(False)
    device.async_set_cooling_mode.assert_not_awaited()


async def test_set_hvac_mode_heat_with_cooling_capable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_hvac_mode(heat) on cooling-capable device also clears cooling_mode."""
    device = _make_climate_device(
        device_id="cc-hvac-heat-cool",
        name="Pool Room",
        summer_mode=False,
        supports_cooling=True,
        cooling_mode=True,
        boost_mode=False,
        low=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Pool Room")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {"entity_id": "climate.pool_room", ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    device.async_set_summer_mode.assert_awaited_once_with(False)
    device.async_set_cooling_mode.assert_awaited_once_with(False)


async def test_set_hvac_mode_cool(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_hvac_mode(cool) calls summer_mode(False) + cooling_mode(True)."""
    device = _make_climate_device(
        device_id="cc-hvac-cool",
        name="Sunroom",
        summer_mode=False,
        supports_cooling=True,
        cooling_mode=False,
        boost_mode=False,
        low=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Sunroom")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {"entity_id": "climate.sunroom", ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )

    device.async_set_summer_mode.assert_awaited_once_with(False)
    device.async_set_cooling_mode.assert_awaited_once_with(True)


async def test_set_hvac_mode_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_hvac_mode(off) calls async_set_summer_mode(True)."""
    device = _make_climate_device(
        device_id="cc-hvac-off",
        name="Nursery",
        summer_mode=False,
        supports_cooling=False,
        boost_mode=False,
        low=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Nursery")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {"entity_id": "climate.nursery", ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    device.async_set_summer_mode.assert_awaited_once_with(True)


async def test_set_hvac_mode_off_clears_cooling_first(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_hvac_mode(off) on cooling-capable device clears cooling_mode before setting summer."""
    device = _make_climate_device(
        device_id="cc-hvac-off-cool",
        name="Pergola",
        summer_mode=False,
        supports_cooling=True,
        cooling_mode=True,
        boost_mode=False,
        low=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Pergola")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {"entity_id": "climate.pergola", ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    device.async_set_cooling_mode.assert_awaited_once_with(False)
    device.async_set_summer_mode.assert_awaited_once_with(True)


async def test_set_hvac_mode_exits_eco_first(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_hvac_mode while in ECO (low) mode first exits ECO before applying the mode (#196)."""
    device = _make_climate_device(
        device_id="cc-eco-exit",
        name="Workshop",
        summer_mode=False,
        supports_cooling=False,
        boost_mode=False,
        low=True,
        supports_low=True,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Workshop")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {"entity_id": "climate.workshop", ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    # async_set_low(False) must be called BEFORE summer_mode
    device.async_set_low.assert_awaited_once_with(False)
    device.async_set_summer_mode.assert_awaited_once_with(True)


async def test_set_preset_mode_boost(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_preset_mode('boost') calls async_set_boost_mode(True)."""
    device = _make_climate_device(
        device_id="cc-preset-boost",
        name="Lounge",
        operation_mode=_CC_OP.MANUAL,
        boost_mode=False,
        supports_boost_mode=True,
        low=False,
        supports_low=True,
        summer_mode=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Lounge")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_preset_mode",
        {"entity_id": "climate.lounge", ATTR_PRESET_MODE: "boost"},
        blocking=True,
    )

    device.async_set_boost_mode.assert_awaited_once_with(True)


async def test_set_preset_mode_eco(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_preset_mode('eco') calls async_set_low(True)."""
    device = _make_climate_device(
        device_id="cc-preset-eco",
        name="Library",
        operation_mode=_CC_OP.MANUAL,
        boost_mode=False,
        supports_boost_mode=True,
        low=False,
        supports_low=True,
        summer_mode=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Library")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_preset_mode",
        {"entity_id": "climate.library", ATTR_PRESET_MODE: "eco"},
        blocking=True,
    )

    device.async_set_low.assert_awaited_once_with(True)


async def test_set_preset_mode_eco_clears_boost_first(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Switching to eco while boost is active first clears boost, then sets low."""
    device = _make_climate_device(
        device_id="cc-preset-eco-clr",
        name="Den",
        operation_mode=_CC_OP.MANUAL,
        boost_mode=True,
        supports_boost_mode=True,
        low=False,
        supports_low=True,
        summer_mode=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Den")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_preset_mode",
        {"entity_id": "climate.den", ATTR_PRESET_MODE: "eco"},
        blocking=True,
    )

    device.async_set_boost_mode.assert_awaited_once_with(False)
    device.async_set_low.assert_awaited_once_with(True)


async def test_set_preset_mode_auto(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_preset_mode('auto') sets operation_mode=AUTOMATIC."""
    device = _make_climate_device(
        device_id="cc-preset-auto",
        name="Terrace",
        operation_mode=_CC_OP.MANUAL,
        boost_mode=False,
        supports_boost_mode=True,
        low=False,
        supports_low=True,
        summer_mode=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Terrace")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_preset_mode",
        {"entity_id": "climate.terrace", ATTR_PRESET_MODE: "auto"},
        blocking=True,
    )

    device.async_set_operation_mode.assert_awaited_once_with(_CC_OP.AUTOMATIC)


async def test_set_preset_mode_manual(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_preset_mode('manual') sets operation_mode=MANUAL."""
    device = _make_climate_device(
        device_id="cc-preset-manual",
        name="Craft Room",
        operation_mode=_CC_OP.AUTOMATIC,
        boost_mode=False,
        supports_boost_mode=True,
        low=False,
        supports_low=True,
        summer_mode=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Craft Room")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_preset_mode",
        {"entity_id": "climate.craft_room", ATTR_PRESET_MODE: "manual"},
        blocking=True,
    )

    device.async_set_operation_mode.assert_awaited_once_with(_CC_OP.MANUAL)


async def test_set_temperature_with_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_temperature with hvac_mode sets mode first, then temperature (no MANUAL override)."""
    device = _make_climate_device(
        device_id="cc-settemp-mode",
        name="Game Room",
        operation_mode=_CC_OP.AUTOMATIC,
        summer_mode=True,  # currently off
        supports_cooling=False,
        boost_mode=False,
        low=False,
    )
    _inject_climate(mock_setup_dependencies, device, room_name="Game Room")

    await setup_integration(hass, mock_config_entry)

    # The service call is issued but hvac_mode=HEAT — the entity's current
    # hvac_mode reads from the (unchanged mock) device; after the set_hvac_mode
    # call the device is still summer_mode=True in the mock, so set_temperature
    # will still see OFF and skip. The important assertions here are about the
    # call ordering.
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {
            "entity_id": "climate.game_room",
            ATTR_TEMPERATURE: 22.0,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )

    # async_set_hvac_mode should have been triggered (summer_mode=False)
    device.async_set_summer_mode.assert_awaited_once_with(False)
    # operation_mode switch must NOT happen because ATTR_HVAC_MODE was provided
    device.async_set_operation_mode.assert_not_awaited()


# ---------------------------------------------------------------------------
# HeatingCircuit — state / attribute tests
# ---------------------------------------------------------------------------


async def test_heating_circuit_auto_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """HC with AUTOMATIC operation_mode has hvac_mode=auto."""
    device = _make_heating_circuit(
        device_id="hc-auto",
        name="Floor Heat",
        setpoint_temperature=20.0,
        operation_mode=_HC_OP.AUTOMATIC,
        on=True,
    )
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.floor_heat")
    assert state is not None
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    assert state.attributes[ATTR_TEMPERATURE] == 20.0
    assert state.attributes["current_temperature"] is None


async def test_heating_circuit_manual_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """HC with MANUAL operation_mode has hvac_mode=heat."""
    device = _make_heating_circuit(
        device_id="hc-manual",
        name="Radiator Circuit",
        setpoint_temperature=21.0,
        operation_mode=_HC_OP.MANUAL,
        on=False,
    )
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.radiator_circuit")
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_heating_circuit_hvac_modes_list(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """HC hvac_modes must be [auto, heat] — no OFF, no COOL."""
    device = _make_heating_circuit(device_id="hc-modes", name="Modes Circuit")
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.modes_circuit")
    assert state is not None
    modes = state.attributes[ATTR_HVAC_MODES]
    assert HVACMode.AUTO in modes
    assert HVACMode.HEAT in modes
    assert HVACMode.OFF not in modes
    assert HVACMode.COOL not in modes


async def test_heating_circuit_no_current_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """HeatingCircuit always returns None for current_temperature."""
    device = _make_heating_circuit(device_id="hc-noct", name="Underfloor")
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.underfloor")
    assert state is not None
    assert state.attributes.get("current_temperature") is None


async def test_heating_circuit_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """HC set_temperature calls async_set_setpoint_temperature with rounded value."""
    device = _make_heating_circuit(
        device_id="hc-settemp",
        name="Underfloor Heat",
        setpoint_temperature=19.0,
        operation_mode=_HC_OP.MANUAL,
    )
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {"entity_id": "climate.underfloor_heat", ATTR_TEMPERATURE: 21.7},
        blocking=True,
    )

    # 21.7 → rounds to 21.5 (nearest 0.5)
    device.async_set_setpoint_temperature.assert_awaited_once_with(21.5)


async def test_heating_circuit_set_temperature_out_of_range_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """HC: HA climate platform rejects temperatures outside [5, 30] before entity sees them."""
    device = _make_heating_circuit(device_id="hc-oob", name="Circuit OOB")
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            "set_temperature",
            {"entity_id": "climate.circuit_oob", ATTR_TEMPERATURE: 1.0},
            blocking=True,
        )

    device.async_set_setpoint_temperature.assert_not_awaited()


async def test_heating_circuit_set_hvac_mode_auto(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """HC set_hvac_mode(auto) writes AUTOMATIC operation mode."""
    device = _make_heating_circuit(
        device_id="hc-hvac-auto",
        name="Auto Circuit",
        operation_mode=_HC_OP.MANUAL,
    )
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {"entity_id": "climate.auto_circuit", ATTR_HVAC_MODE: HVACMode.AUTO},
        blocking=True,
    )

    device.async_set_operation_mode.assert_awaited_once_with(_HC_OP.AUTOMATIC)


async def test_heating_circuit_set_hvac_mode_heat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """HC set_hvac_mode(heat) writes MANUAL operation mode."""
    device = _make_heating_circuit(
        device_id="hc-hvac-heat",
        name="Heat Circuit",
        operation_mode=_HC_OP.AUTOMATIC,
    )
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {"entity_id": "climate.heat_circuit", ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    device.async_set_operation_mode.assert_awaited_once_with(_HC_OP.MANUAL)


async def test_heating_circuit_set_hvac_mode_invalid_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """HC: HA climate platform rejects hvac_mode values not in hvac_modes (e.g. OFF)."""
    device = _make_heating_circuit(device_id="hc-invalid", name="Invalid Circuit")
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            "set_hvac_mode",
            {"entity_id": "climate.invalid_circuit", ATTR_HVAC_MODE: HVACMode.OFF},
            blocking=True,
        )

    device.async_set_operation_mode.assert_not_awaited()


# ---------------------------------------------------------------------------
# Excluded / empty collections
# ---------------------------------------------------------------------------


async def test_no_climate_entities_when_collections_empty(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """No climate entities are created when both collections are empty."""
    mock_setup_dependencies.device_helper.climate_controls = []
    mock_setup_dependencies.device_helper.heating_circuits = []

    await setup_integration(hass, mock_config_entry)

    assert len(hass.states.async_all(CLIMATE_DOMAIN)) == 0


async def test_excluded_climate_device_not_added(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """A climate_control in OPT_EXCLUDED_DEVICES is skipped."""
    device = _make_climate_device(device_id="excluded-cc", name="Excluded Room")
    _inject_climate(mock_setup_dependencies, device, room_name="Excluded Room")

    entry = _make_config_entry_with_options({OPT_EXCLUDED_DEVICES: ["excluded-cc"]})
    await setup_integration(hass, entry)

    assert hass.states.get("climate.excluded_room") is None


async def test_excluded_heating_circuit_not_added(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """A heating_circuit in OPT_EXCLUDED_DEVICES is skipped."""
    device = _make_heating_circuit(device_id="excluded-hc", name="Excluded Circuit")
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    entry = _make_config_entry_with_options({OPT_EXCLUDED_DEVICES: ["excluded-hc"]})
    await setup_integration(hass, entry)

    assert hass.states.get("climate.excluded_circuit") is None


# ---------------------------------------------------------------------------
# Unique ID / registry
# ---------------------------------------------------------------------------


async def test_climate_control_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """ClimateControl unique_id = root_device_id + '_' + device_id."""
    device = _make_climate_device(device_id="cc-uid", name="Uid Room")
    device.root_device_id = "shc-root"
    _inject_climate(mock_setup_dependencies, device, room_name="Uid Room")

    await setup_integration(hass, mock_config_entry)

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("climate.uid_room")
    assert entry is not None
    assert entry.unique_id == "shc-root_cc-uid"


async def test_heating_circuit_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """HeatingCircuit unique_id = root_device_id + '_' + device_id."""
    device = _make_heating_circuit(device_id="hc-uid", name="Uid Circuit")
    device.root_device_id = "shc-root"
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("climate.uid_circuit")
    assert entry is not None
    assert entry.unique_id == "shc-root_hc-uid"
