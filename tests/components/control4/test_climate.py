"""Test Control4 Climate."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "climate.test_controller_residential_thermostat_v2"


def _make_climate_data(
    hvac_state: str = "off",
    hvac_mode: str = "Heat",
    temperature: float = 72.0,
    humidity: int = 50,
    cool_setpoint: float = 75.0,
    heat_setpoint: float = 68.0,
    scale: str = "FAHRENHEIT",
) -> dict[int, dict[str, Any]]:
    """Build mock climate variable data for item ID 123 (Fahrenheit)."""
    return {
        123: {
            "HVAC_STATE": hvac_state,
            "HVAC_MODE": hvac_mode,
            "TEMPERATURE_F": temperature,
            "HUMIDITY": humidity,
            "COOL_SETPOINT_F": cool_setpoint,
            "HEAT_SETPOINT_F": heat_setpoint,
            "SCALE": scale,
        }
    }


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms which should be loaded during the test."""
    return [Platform.CLIMATE]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Control4 integration for testing."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_climate_update_variables",
    "init_integration",
)
async def test_climate_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate entities are set up correctly with proper attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("mock_climate_variables", "expected_action"),
    [
        pytest.param(
            _make_climate_data(hvac_state="Off", hvac_mode="Off"),
            HVACAction.OFF,
            id="off",
        ),
        pytest.param(
            _make_climate_data(hvac_state="Heat"),
            HVACAction.HEATING,
            id="heat",
        ),
        pytest.param(
            _make_climate_data(hvac_state="Cool", hvac_mode="Cool"),
            HVACAction.COOLING,
            id="cool",
        ),
        pytest.param(
            _make_climate_data(hvac_state="Dry"),
            HVACAction.DRYING,
            id="dry",
        ),
        pytest.param(
            _make_climate_data(hvac_state="Fan"),
            HVACAction.FAN,
            id="fan",
        ),
    ],
)
@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_climate_update_variables",
    "init_integration",
)
async def test_hvac_action_mapping(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    expected_action: HVACAction,
) -> None:
    """Test all 5 official Control4 HVAC states map to correct HA actions."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["hvac_action"] == expected_action


@pytest.mark.parametrize(
    (
        "mock_climate_variables",
        "expected_hvac_mode",
        "expected_hvac_action",
        "expected_temperature",
        "expected_temp_high",
        "expected_temp_low",
    ),
    [
        pytest.param(
            _make_climate_data(hvac_state="Off", hvac_mode="Off"),
            HVACMode.OFF,
            HVACAction.OFF,
            None,
            None,
            None,
            id="off",
        ),
        pytest.param(
            _make_climate_data(
                hvac_state="Cool",
                hvac_mode="Cool",
                temperature=74.0,
                humidity=55,
                cool_setpoint=72.0,
            ),
            HVACMode.COOL,
            HVACAction.COOLING,
            72.0,
            None,
            None,
            id="cool",
        ),
        pytest.param(
            _make_climate_data(
                hvac_state="Heat",
                hvac_mode="Auto",
                temperature=65.0,
                humidity=40,
            ),
            HVACMode.HEAT_COOL,
            HVACAction.HEATING,
            None,
            75.0,
            68.0,
            id="auto",
        ),
    ],
)
@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_climate_update_variables",
    "init_integration",
)
async def test_climate_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    expected_hvac_mode: HVACMode,
    expected_hvac_action: HVACAction,
    expected_temperature: float | None,
    expected_temp_high: float | None,
    expected_temp_low: float | None,
) -> None:
    """Test climate entity in different states."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected_hvac_mode
    assert state.attributes["hvac_action"] == expected_hvac_action

    assert state.attributes.get("temperature") == expected_temperature

    assert state.attributes.get("target_temp_high") == expected_temp_high
    assert state.attributes.get("target_temp_low") == expected_temp_low


@pytest.mark.parametrize(
    ("hvac_mode", "expected_c4_mode"),
    [
        pytest.param(HVACMode.COOL, "Cool", id="cool"),
        pytest.param(HVACMode.OFF, "Off", id="off"),
    ],
)
@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_climate_update_variables",
    "init_integration",
)
async def test_set_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_climate: MagicMock,
    hvac_mode: HVACMode,
    expected_c4_mode: str,
) -> None:
    """Test setting HVAC mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )
    mock_c4_climate.setHvacMode.assert_called_once_with(expected_c4_mode)


@pytest.mark.parametrize(
    ("mock_climate_variables", "method_name"),
    [
        pytest.param(
            _make_climate_data(
                hvac_state="Off",
                temperature=72.5,
                humidity=45,
            ),
            "setHeatSetpointF",
            id="heat",
        ),
        pytest.param(
            _make_climate_data(
                hvac_state="Cool",
                hvac_mode="Cool",
                temperature=74.0,
                cool_setpoint=72.0,
            ),
            "setCoolSetpointF",
            id="cool",
        ),
    ],
)
@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_climate_update_variables",
    "init_integration",
)
async def test_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_climate: MagicMock,
    method_name: str,
) -> None:
    """Test setting temperature in different modes."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 70.0},
        blocking=True,
    )
    getattr(mock_c4_climate, method_name).assert_called_once_with(70.0)


@pytest.mark.parametrize(
    "mock_climate_variables",
    [
        _make_climate_data(hvac_state="Off", hvac_mode="Auto"),
    ],
)
@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_climate_update_variables",
    "init_integration",
)
async def test_set_temperature_range_auto_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_climate: MagicMock,
) -> None:
    """Test setting temperature range in auto mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TARGET_TEMP_LOW: 65.0,
            ATTR_TARGET_TEMP_HIGH: 78.0,
        },
        blocking=True,
    )
    mock_c4_climate.setHeatSetpointF.assert_called_once_with(65.0)
    mock_c4_climate.setCoolSetpointF.assert_called_once_with(78.0)


@pytest.mark.parametrize("mock_climate_variables", [{}])
@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_climate_update_variables",
    "init_integration",
)
async def test_climate_not_created_when_no_initial_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate entity is not created when coordinator has no initial data."""
    # Entity should not be created if there's no data during initial setup
    state = hass.states.get(ENTITY_ID)
    assert state is None


@pytest.mark.parametrize(
    "mock_climate_variables",
    [
        {
            123: {
                "HVAC_STATE": "Off",
                "HVAC_MODE": "Heat",
                # Missing TEMPERATURE_F and HUMIDITY
                "COOL_SETPOINT_F": 75.0,
                "HEAT_SETPOINT_F": 68.0,
                "SCALE": "FAHRENHEIT",
            }
        }
    ],
)
@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_climate_update_variables",
    "init_integration",
)
async def test_climate_missing_variables(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate entity handles missing variables gracefully."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes.get("current_temperature") is None
    assert state.attributes.get("current_humidity") is None
    assert state.attributes["temperature"] == 68.0


@pytest.mark.parametrize(
    "mock_climate_variables",
    [
        _make_climate_data(hvac_state="off", hvac_mode="UnknownMode"),
    ],
)
@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_climate_update_variables",
    "init_integration",
)
async def test_climate_unknown_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate entity handles unknown HVAC mode."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF  # Defaults to OFF for unknown modes


@pytest.mark.parametrize(
    "mock_climate_variables",
    [
        _make_climate_data(hvac_state="unknown_state"),
    ],
)
@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_climate_update_variables",
    "init_integration",
)
async def test_climate_unknown_hvac_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate entity handles unknown HVAC state."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get("hvac_action") is None


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_climate_update_variables",
    "init_integration",
)
async def test_set_fan_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_climate: MagicMock,
) -> None:
    """Test setting fan mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "on"},
        blocking=True,
    )
    # Verify the Control4 API is called with the C4 format ("On" not "on")
    mock_c4_climate.setFanMode.assert_called_once_with("On")


@pytest.mark.parametrize(
    "mock_climate_variables",
    [
        {
            123: {
                "HVAC_STATE": "idle",
                "HVAC_MODE": "Heat",
                "TEMPERATURE_F": 72.0,
                "HUMIDITY": 50,
                "COOL_SETPOINT_F": 75.0,
                "HEAT_SETPOINT_F": 68.0,
                "SCALE": "FAHRENHEIT",
                # No FAN_MODE or FAN_MODES_LIST
            }
        }
    ],
)
@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_climate_update_variables",
    "init_integration",
)
async def test_fan_mode_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test fan mode feature not set when device doesn't support it."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get("fan_mode") is None
    assert state.attributes.get("fan_modes") is None
    assert not (
        state.attributes.get("supported_features") & ClimateEntityFeature.FAN_MODE
    )


# Temperature unit tests - verify correct API methods are called based on SCALE


@pytest.mark.parametrize(
    ("mock_climate_variables", "expected_method", "unexpected_method"),
    [
        pytest.param(
            _make_climate_data(hvac_state="Off", hvac_mode="Heat"),
            "setHeatSetpointF",
            "setHeatSetpointC",
            id="fahrenheit_heat_calls_F_not_C",
        ),
        pytest.param(
            _make_climate_data(hvac_state="Cool", hvac_mode="Cool"),
            "setCoolSetpointF",
            "setCoolSetpointC",
            id="fahrenheit_cool_calls_F_not_C",
        ),
    ],
)
@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_climate_update_variables",
    "init_integration",
)
async def test_set_temperature_calls_correct_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_climate: MagicMock,
    expected_method: str,
    unexpected_method: str,
) -> None:
    """Test setting temperature calls correct API method based on SCALE.

    Verifies that when setting temperature:
    - The correct method for the scale is called
    - The wrong scale's method is NOT called
    """
    # Reset mock to clear any calls from previous parametrized test runs
    mock_c4_climate.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 70.0},
        blocking=True,
    )
    getattr(mock_c4_climate, expected_method).assert_called_once_with(70.0)
    getattr(mock_c4_climate, unexpected_method).assert_not_called()
