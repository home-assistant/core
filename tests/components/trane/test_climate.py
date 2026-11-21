"""Tests for the Trane Local climate platform."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from steamloop import FanMode, HoldType, ZoneMode
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    ClimateService,
    ClimateServiceArgument,
    HVACAction,
    HVACMode,
)

from homeassistant.components.trane.const import ATTR_DEADBAND
from homeassistant.const import Platform, TargetKey

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.CLIMATE]


@pytest.fixture(autouse=True)
def set_us_customary(hass: HomeAssistant) -> None:
    """Set US customary unit system for Trane (Fahrenheit thermostats)."""
    hass.config.units = US_CUSTOMARY_SYSTEM


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_climate_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot all climate entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_hvac_mode_auto(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test HVAC mode is AUTO when following schedule."""
    mock_connection.state.zones["1"].hold_type = HoldType.SCHEDULE

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room_living_room")
    assert state is not None
    assert state.state == HVACMode.AUTO


async def test_current_temperature_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test current temperature is None when not yet received."""
    mock_connection.state.zones["1"].indoor_temperature = ""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room_living_room")
    assert state is not None
    assert state.attributes["current_temperature"] is None


async def test_current_humidity_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test current humidity is omitted when not yet received."""
    mock_connection.state.relative_humidity = ""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room_living_room")
    assert state is not None
    assert "current_humidity" not in state.attributes


async def test_set_hvac_mode_off(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test setting HVAC mode to off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_HVAC_MODE,
        {
            TargetKey.ENTITY_ID: "climate.living_room_living_room",
            ClimateServiceArgument.HVAC_MODE: HVACMode.OFF,
        },
        blocking=True,
    )

    mock_connection.set_temperature_setpoint.assert_not_called()
    mock_connection.set_zone_mode.assert_called_once_with("1", ZoneMode.OFF)


@pytest.mark.parametrize(
    ("hvac_mode", "expected_hold", "expected_zone_mode"),
    [
        (HVACMode.AUTO, HoldType.SCHEDULE, ZoneMode.AUTO),
        (HVACMode.HEAT_COOL, HoldType.MANUAL, ZoneMode.AUTO),
        (HVACMode.HEAT, HoldType.MANUAL, ZoneMode.HEAT),
        (HVACMode.COOL, HoldType.MANUAL, ZoneMode.COOL),
    ],
)
async def test_set_hvac_mode(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MagicMock,
    hvac_mode: HVACMode,
    expected_hold: HoldType,
    expected_zone_mode: ZoneMode,
) -> None:
    """Test setting HVAC mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_HVAC_MODE,
        {
            TargetKey.ENTITY_ID: "climate.living_room_living_room",
            ClimateServiceArgument.HVAC_MODE: hvac_mode,
        },
        blocking=True,
    )

    mock_connection.set_temperature_setpoint.assert_called_once_with(
        "1", hold_type=expected_hold
    )
    mock_connection.set_zone_mode.assert_called_once_with("1", expected_zone_mode)


async def test_set_temperature_range(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test setting temperature range in heat_cool mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_TEMPERATURE,
        {
            TargetKey.ENTITY_ID: "climate.living_room_living_room",
            ClimateServiceArgument.TARGET_TEMP_LOW: 65,
            ClimateServiceArgument.TARGET_TEMP_HIGH: 78,
        },
        blocking=True,
    )

    mock_connection.set_temperature_setpoint.assert_called_once_with(
        "1",
        heat_setpoint="65",
        cool_setpoint="78",
    )


async def test_set_temperature_single_heat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test setting single temperature in heat mode."""
    mock_connection.state.zones["1"].mode = ZoneMode.HEAT

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_TEMPERATURE,
        {
            TargetKey.ENTITY_ID: "climate.living_room_living_room",
            ClimateServiceArgument.TEMPERATURE: 70,
        },
        blocking=True,
    )

    mock_connection.set_temperature_setpoint.assert_called_once_with(
        "1",
        heat_setpoint="70",
        cool_setpoint=None,
    )


async def test_set_temperature_single_cool(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test setting single temperature in cool mode."""
    mock_connection.state.zones["1"].mode = ZoneMode.COOL

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_TEMPERATURE,
        {
            TargetKey.ENTITY_ID: "climate.living_room_living_room",
            ClimateServiceArgument.TEMPERATURE: 78,
        },
        blocking=True,
    )

    mock_connection.set_temperature_setpoint.assert_called_once_with(
        "1",
        heat_setpoint=None,
        cool_setpoint="78",
    )


@pytest.mark.parametrize(
    ("fan_mode", "expected_fan_mode"),
    [
        ("auto", FanMode.AUTO),
        ("on", FanMode.ALWAYS_ON),
        ("circulate", FanMode.CIRCULATE),
    ],
)
async def test_set_fan_mode(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MagicMock,
    fan_mode: str,
    expected_fan_mode: FanMode,
) -> None:
    """Test setting fan mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_FAN_MODE,
        {
            TargetKey.ENTITY_ID: "climate.living_room_living_room",
            ClimateServiceArgument.FAN_MODE: fan_mode,
        },
        blocking=True,
    )

    mock_connection.set_fan_mode.assert_called_once_with(expected_fan_mode)


@pytest.mark.parametrize(
    ("cooling_active", "heating_active", "zone_mode", "expected_action"),
    [
        ("0", "0", ZoneMode.OFF, HVACAction.OFF),
        ("0", "2", ZoneMode.AUTO, HVACAction.HEATING),
        ("2", "0", ZoneMode.AUTO, HVACAction.COOLING),
        ("0", "0", ZoneMode.AUTO, HVACAction.IDLE),
        ("0", "1", ZoneMode.AUTO, HVACAction.IDLE),
        ("1", "0", ZoneMode.AUTO, HVACAction.IDLE),
        ("0", "2", ZoneMode.COOL, HVACAction.IDLE),
        ("2", "0", ZoneMode.HEAT, HVACAction.IDLE),
        ("2", "2", ZoneMode.AUTO, HVACAction.COOLING),
    ],
)
async def test_hvac_action(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    cooling_active: str,
    heating_active: str,
    zone_mode: ZoneMode,
    expected_action: HVACAction,
) -> None:
    """Test HVAC action reflects thermostat state."""
    mock_connection.state.cooling_active = cooling_active
    mock_connection.state.heating_active = heating_active
    mock_connection.state.zones["1"].mode = zone_mode

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room_living_room")
    assert state is not None
    assert state.attributes["hvac_action"] == expected_action


async def test_turn_on(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test turn on defaults to heat_cool mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.TURN_ON,
        {TargetKey.ENTITY_ID: "climate.living_room_living_room"},
        blocking=True,
    )

    mock_connection.set_temperature_setpoint.assert_called_once_with(
        "1", hold_type=HoldType.MANUAL
    )
    mock_connection.set_zone_mode.assert_called_once_with("1", ZoneMode.AUTO)


async def test_turn_off(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test turn off sets mode to off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.TURN_OFF,
        {TargetKey.ENTITY_ID: "climate.living_room_living_room"},
        blocking=True,
    )

    mock_connection.set_temperature_setpoint.assert_not_called()
    mock_connection.set_zone_mode.assert_called_once_with("1", ZoneMode.OFF)


async def test_deadband_attribute(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test the dead band reported by the thermostat is exposed as an attribute."""
    mock_connection.state.zones["1"].deadband = "5"

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room_living_room")
    assert state is not None
    assert state.attributes[ATTR_DEADBAND] == 5.0


async def test_deadband_attribute_before_first_report(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test the dead band attribute is absent until the thermostat reports one."""
    mock_connection.state.zones["1"].deadband = ""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room_living_room")
    assert state is not None
    assert ATTR_DEADBAND not in state.attributes
