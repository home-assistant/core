"""Tests for the Bosch SHC climate platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from boschshcpy import HeatingCircuitService, RoomClimateControlService
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODES,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import climate_control_device, heating_circuit_device, setup_integration

ENTITY_ID = "climate.living_room"
AUTOMATIC = RoomClimateControlService.OperationMode.AUTOMATIC
MANUAL = RoomClimateControlService.OperationMode.MANUAL


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the climate platform."""
    with patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.CLIMATE]):
        yield


@pytest.fixture(autouse=True)
def room_name(mock_session: MagicMock) -> None:
    """Give the mocked session a named room."""
    mock_session.room.return_value.name = "Living Room"


@pytest.mark.parametrize(
    ("device_kwargs", "hvac_mode", "hvac_action"),
    [
        ({}, HVACMode.AUTO, HVACAction.IDLE),
        ({"has_demand": True}, HVACMode.AUTO, HVACAction.HEATING),
        ({"operation_mode": MANUAL}, HVACMode.HEAT, HVACAction.IDLE),
        ({"summer_mode": True}, HVACMode.OFF, HVACAction.OFF),
        (
            {"supports_cooling": True, "cooling_mode": True},
            HVACMode.COOL,
            HVACAction.IDLE,
        ),
        (
            {"supports_cooling": True, "cooling_mode": True, "has_demand": True},
            HVACMode.COOL,
            HVACAction.COOLING,
        ),
    ],
    ids=["auto", "heating", "manual", "off", "cooling-idle", "cooling"],
)
async def test_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    device_kwargs: dict,
    hvac_mode: HVACMode,
    hvac_action: HVACAction,
) -> None:
    """The room state maps onto HVAC mode and action."""
    mock_session.device_helper.climate_controls = [
        climate_control_device(**device_kwargs)
    ]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == hvac_mode
    assert state.attributes[ATTR_HVAC_ACTION] == hvac_action
    assert state.attributes["current_temperature"] == 20.5
    assert state.attributes[ATTR_TEMPERATURE] == 21.0


@pytest.mark.parametrize(
    ("supports_cooling", "supports_boost_mode", "supports_eco", "modes", "presets"),
    [
        (
            True,
            True,
            True,
            [HVACMode.AUTO, HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
            [PRESET_NONE, PRESET_BOOST, PRESET_ECO],
        ),
        (
            False,
            False,
            False,
            [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF],
            None,
        ),
    ],
    ids=["full", "minimal"],
)
async def test_capabilities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    supports_cooling: bool,
    supports_boost_mode: bool,
    supports_eco: bool,
    modes: list[HVACMode],
    presets: list[str] | None,
) -> None:
    """Cooling and presets are only offered when the room supports them."""
    mock_session.device_helper.climate_controls = [
        climate_control_device(
            supports_cooling=supports_cooling,
            supports_boost_mode=supports_boost_mode,
            supports_eco=supports_eco,
        )
    ]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_HVAC_MODES] == modes
    assert state.attributes.get(ATTR_PRESET_MODES) == presets


@pytest.mark.parametrize(
    ("preset", "boost_mode", "low"),
    [(PRESET_BOOST, True, False), (PRESET_ECO, False, True)],
    ids=["boost", "eco"],
)
async def test_active_preset(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    preset: str,
    boost_mode: bool,
    low: bool,
) -> None:
    """The active override is reported as preset."""
    mock_session.device_helper.climate_controls = [
        climate_control_device(boost_mode=boost_mode, low=low)
    ]
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).attributes["preset_mode"] == preset


@pytest.mark.parametrize(
    ("hvac_mode", "attr", "value"),
    [
        (HVACMode.OFF, "summer_mode", True),
        (HVACMode.COOL, "cooling_mode", True),
        (HVACMode.HEAT, "operation_mode", MANUAL),
        (HVACMode.AUTO, "operation_mode", AUTOMATIC),
    ],
)
async def test_set_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    hvac_mode: HVACMode,
    attr: str,
    value: object,
) -> None:
    """Setting an HVAC mode writes the matching device field."""
    device = climate_control_device(supports_cooling=True)
    mock_session.device_helper.climate_controls = [device]
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, "hvac_mode": hvac_mode},
        blocking=True,
    )

    assert getattr(device, attr) == value


async def test_set_hvac_mode_leaves_summer_mode_and_eco(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """Leaving off or eco clears the blocking flags first."""
    device = climate_control_device(summer_mode=True, low=True)
    mock_session.device_helper.climate_controls = [device]
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )

    assert device.summer_mode is False
    assert device.low is False
    assert device.operation_mode == MANUAL


async def test_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """Setting a temperature leaves eco and writes the setpoint."""
    device = climate_control_device(low=True)
    mock_session.device_helper.climate_controls = [device]
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22.5},
        blocking=True,
    )

    assert device.low is False
    assert device.setpoint_temperature == 22.5


async def test_set_temperature_while_off_is_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """A setpoint is not written while the room is off."""
    device = climate_control_device(summer_mode=True)
    mock_session.device_helper.climate_controls = [device]
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22.5},
        blocking=True,
    )

    assert device.setpoint_temperature == 21.0


async def test_set_temperature_with_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """A combined call turns the room on before writing the setpoint."""
    device = climate_control_device(summer_mode=True)
    mock_session.device_helper.climate_controls = [device]
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 22.5,
            "hvac_mode": HVACMode.HEAT,
        },
        blocking=True,
    )

    assert device.summer_mode is False
    assert device.setpoint_temperature == 22.5


async def test_set_preset_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """Eco clears boost first, boost sets boost mode."""
    device = climate_control_device(boost_mode=True)
    mock_session.device_helper.climate_controls = [device]
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, "preset_mode": PRESET_ECO},
        blocking=True,
    )
    assert device.boost_mode is False
    assert device.low is True

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, "preset_mode": PRESET_BOOST},
        blocking=True,
    )
    assert device.boost_mode is True


@pytest.mark.parametrize(
    ("device_kwargs", "boost_mode", "low"),
    [({"boost_mode": True}, False, False), ({"low": True}, False, False)],
    ids=["cancel-boost", "cancel-eco"],
)
async def test_cancel_preset(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    device_kwargs: dict,
    boost_mode: bool,
    low: bool,
) -> None:
    """The none preset clears boost and eco."""
    device = climate_control_device(**device_kwargs)
    mock_session.device_helper.climate_controls = [device]
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, "preset_mode": PRESET_NONE},
        blocking=True,
    )

    assert device.boost_mode is boost_mode
    assert device.low is low


@pytest.mark.parametrize("hvac_mode", [HVACMode.COOL, HVACMode.FAN_ONLY])
async def test_set_temperature_unsupported_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    hvac_mode: HVACMode,
) -> None:
    """A combined call with an unsupported HVAC mode changes nothing."""
    device = climate_control_device(low=True)
    mock_session.device_helper.climate_controls = [device]
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_TEMPERATURE: 22.5,
                "hvac_mode": hvac_mode,
            },
            blocking=True,
        )

    assert device.low is True
    assert device.setpoint_temperature == 21.0


async def test_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """Turn off enables summer mode, turn on returns to automatic."""
    device = climate_control_device()
    mock_session.device_helper.climate_controls = [device]
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert device.summer_mode is True

    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert device.summer_mode is False
    assert device.operation_mode == AUTOMATIC


HC_ENTITY_ID = "climate.floor_heating"
HC_AUTOMATIC = HeatingCircuitService.OperationMode.AUTOMATIC
HC_MANUAL = HeatingCircuitService.OperationMode.MANUAL


@pytest.mark.parametrize(
    ("device_kwargs", "hvac_mode", "hvac_action"),
    [
        ({}, HVACMode.AUTO, HVACAction.IDLE),
        ({"on": True}, HVACMode.AUTO, HVACAction.HEATING),
        ({"operation_mode": HC_MANUAL}, HVACMode.HEAT, HVACAction.IDLE),
    ],
    ids=["auto", "heating", "manual"],
)
async def test_heating_circuit_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    device_kwargs: dict,
    hvac_mode: HVACMode,
    hvac_action: HVACAction,
) -> None:
    """The heating circuit state maps onto HVAC mode and action."""
    mock_session.device_helper.heating_circuits = [
        heating_circuit_device(**device_kwargs)
    ]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(HC_ENTITY_ID)
    assert state is not None
    assert state.state == hvac_mode
    assert state.attributes[ATTR_HVAC_ACTION] == hvac_action
    assert state.attributes[ATTR_TEMPERATURE] == 22.0
    assert state.attributes["current_temperature"] is None


@pytest.mark.parametrize(
    ("temperature_range", "min_temp", "max_temp"),
    [((5.0, 30.0), 5.0, 30.0), ((15.0, 28.0), 15.0, 28.0), (None, 5.0, 30.0)],
    ids=["default", "raised-minimum", "unreported"],
)
async def test_heating_circuit_temperature_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    temperature_range: tuple[float, float] | None,
    min_temp: float,
    max_temp: float,
) -> None:
    """The setpoint range follows the device and falls back to 5-30 °C."""
    mock_session.device_helper.heating_circuits = [
        heating_circuit_device(setpoint_temperature_range=temperature_range)
    ]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(HC_ENTITY_ID)
    assert state is not None
    assert state.attributes["min_temp"] == min_temp
    assert state.attributes["max_temp"] == max_temp


@pytest.mark.parametrize(
    ("hvac_mode", "value"),
    [(HVACMode.AUTO, HC_AUTOMATIC), (HVACMode.HEAT, HC_MANUAL)],
)
async def test_heating_circuit_set_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    hvac_mode: HVACMode,
    value: HeatingCircuitService.OperationMode,
) -> None:
    """Setting an HVAC mode writes the operation mode."""
    device = heating_circuit_device()
    mock_session.device_helper.heating_circuits = [device]
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: HC_ENTITY_ID, "hvac_mode": hvac_mode},
        blocking=True,
    )

    assert device.operation_mode == value


async def test_heating_circuit_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """Setting the temperature writes the setpoint."""
    device = heating_circuit_device()
    mock_session.device_helper.heating_circuits = [device]
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: HC_ENTITY_ID, ATTR_TEMPERATURE: 24.0},
        blocking=True,
    )

    assert device.setpoint_temperature == 24.0


async def test_heating_circuit_set_temperature_with_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """A combined call applies the mode and the setpoint."""
    device = heating_circuit_device(operation_mode=HC_AUTOMATIC)
    mock_session.device_helper.heating_circuits = [device]
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: HC_ENTITY_ID,
            ATTR_TEMPERATURE: 24.0,
            "hvac_mode": HVACMode.HEAT,
        },
        blocking=True,
    )

    assert device.operation_mode == HC_MANUAL
    assert device.setpoint_temperature == 24.0


async def test_heating_circuit_set_temperature_unsupported_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """An unsupported mode in a combined call changes nothing."""
    device = heating_circuit_device(operation_mode=HC_AUTOMATIC)
    mock_session.device_helper.heating_circuits = [device]
    await setup_integration(hass, mock_config_entry)
    setpoint = device.setpoint_temperature

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: HC_ENTITY_ID,
                ATTR_TEMPERATURE: 24.0,
                "hvac_mode": HVACMode.COOL,
            },
            blocking=True,
        )

    assert device.operation_mode == HC_AUTOMATIC
    assert device.setpoint_temperature == setpoint
