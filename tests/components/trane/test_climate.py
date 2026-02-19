"""Tests for the Trane Local climate platform."""

from unittest.mock import MagicMock

import pytest
from steamloop import FanMode, HoldType, ZoneMode
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
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
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import MockConfigEntry, snapshot_platform


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


async def test_hvac_mode_heat_cool(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test HVAC mode is HEAT_COOL when AUTO with permanent hold."""
    state = hass.states.get("climate.living_room")
    assert state is not None
    assert state.state == HVACMode.HEAT_COOL


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

    state = hass.states.get("climate.living_room")
    assert state is not None
    assert state.state == HVACMode.AUTO


@pytest.mark.parametrize(
    ("hvac_mode", "expected_hold", "expected_zone_mode"),
    [
        (HVACMode.OFF, None, ZoneMode.OFF),
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
    expected_hold: HoldType | None,
    expected_zone_mode: ZoneMode,
) -> None:
    """Test setting HVAC mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    if expected_hold is not None:
        mock_connection.set_temperature_setpoint.assert_called_once_with(
            "1", hold_type=expected_hold
        )
    else:
        mock_connection.set_temperature_setpoint.assert_not_called()

    mock_connection.set_zone_mode.assert_called_once_with("1", expected_zone_mode)


async def test_set_temperature_range(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test setting temperature range in heat_cool mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.living_room",
            ATTR_TARGET_TEMP_LOW: 65,
            ATTR_TARGET_TEMP_HIGH: 78,
        },
        blocking=True,
    )

    mock_connection.set_temperature_setpoint.assert_called_once_with(
        "1",
        heat_setpoint="65",
        cool_setpoint="78",
    )


async def test_set_temperature_single(
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
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.living_room",
            ATTR_TEMPERATURE: 70,
        },
        blocking=True,
    )

    mock_connection.set_temperature_setpoint.assert_called_once_with(
        "1",
        heat_setpoint="70",
        cool_setpoint=None,
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
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_FAN_MODE: fan_mode},
        blocking=True,
    )

    mock_connection.set_fan_mode.assert_called_once_with(expected_fan_mode)


@pytest.mark.parametrize(
    ("cooling_active", "heating_active", "zone_mode", "expected_action"),
    [
        ("", "", ZoneMode.OFF, HVACAction.OFF),
        ("", "1", ZoneMode.AUTO, HVACAction.HEATING),
        ("1", "", ZoneMode.AUTO, HVACAction.COOLING),
        ("", "", ZoneMode.AUTO, HVACAction.IDLE),
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

    state = hass.states.get("climate.living_room")
    assert state is not None
    assert state.attributes["hvac_action"] == expected_action


@pytest.mark.parametrize(
    ("service", "expected_hold", "expected_zone_mode"),
    [
        (SERVICE_TURN_ON, HoldType.SCHEDULE, ZoneMode.AUTO),
        (SERVICE_TURN_OFF, None, ZoneMode.OFF),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MagicMock,
    service: str,
    expected_hold: HoldType | None,
    expected_zone_mode: ZoneMode,
) -> None:
    """Test turn on and turn off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "climate.living_room"},
        blocking=True,
    )

    if expected_hold is not None:
        mock_connection.set_temperature_setpoint.assert_called_once_with(
            "1", hold_type=expected_hold
        )
    else:
        mock_connection.set_temperature_setpoint.assert_not_called()

    mock_connection.set_zone_mode.assert_called_once_with("1", expected_zone_mode)
