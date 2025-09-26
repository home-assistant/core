"""Tests for the Niko Home Control Climate platform."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import ATTR_HVAC_MODE, ATTR_PRESET_MODE, HVACMode
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import find_update_callback, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.niko_home_control.PLATFORMS", [Platform.CLIMATE]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_temperature(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    climate: AsyncMock,
) -> None:
    """Test setting a temperature."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: "climate.thermostat", "temperature": 25},
        blocking=True,
    )
    mock_niko_home_control_connection.thermostats[
        "thermostat-5"
    ].set_temperature.assert_called_once_with(25)


async def test_set_preset(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    climate: AsyncMock,
) -> None:
    """Test setting a preset."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {ATTR_ENTITY_ID: "climate.thermostat", ATTR_PRESET_MODE: "eco"},
        blocking=True,
    )
    mock_niko_home_control_connection.thermostats[
        "thermostat-5"
    ].set_mode.assert_called_once_with(2)


async def test_set_hvac_cool_mode(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    climate: AsyncMock,
) -> None:
    """Test setting cool mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )
    mock_niko_home_control_connection.thermostats[
        "thermostat-5"
    ].set_mode.assert_called_once_with(4)


async def test_set_hvac_off_mode(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    climate: AsyncMock,
) -> None:
    """Test setting off mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    mock_niko_home_control_connection.thermostats[
        "thermostat-5"
    ].set_mode.assert_called_once_with(3)


async def test_set_hvac_auto_mode(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    climate: AsyncMock,
) -> None:
    """Test setting auto mode."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: HVACMode.AUTO},
        blocking=True,
    )
    mock_niko_home_control_connection.thermostats[
        "thermostat-5"
    ].set_mode.assert_called_once_with(5)


async def test_turn_off(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    climate: AsyncMock,
) -> None:
    """Test turning off the thermostat."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        "climate",
        "turn_off",
        {ATTR_ENTITY_ID: "climate.thermostat"},
        blocking=True,
    )
    mock_niko_home_control_connection.thermostats[
        "thermostat-5"
    ].set_mode.assert_called_once_with(3)


async def test_updating(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    climate: AsyncMock,
) -> None:
    """Test updating the thermostat."""
    await setup_integration(hass, mock_config_entry)

    climate.state = 0
    await find_update_callback(mock_niko_home_control_connection, 5)(0)
    assert hass.states.get("climate.thermostat").attributes.get("preset_mode") == "day"
    assert hass.states.get("climate.thermostat").state == "auto"

    climate.state = 1
    await find_update_callback(mock_niko_home_control_connection, 5)(1)
    assert (
        hass.states.get("climate.thermostat").attributes.get("preset_mode") == "night"
    )
    assert hass.states.get("climate.thermostat").state == "auto"

    climate.state = 2
    await find_update_callback(mock_niko_home_control_connection, 5)(2)
    assert hass.states.get("climate.thermostat").state == "auto"
    assert hass.states.get("climate.thermostat").attributes["preset_mode"] == "eco"

    climate.state = 3
    await find_update_callback(mock_niko_home_control_connection, 5)(3)
    assert hass.states.get("climate.thermostat").state == "off"

    climate.state = 4
    await find_update_callback(mock_niko_home_control_connection, 5)(4)
    assert hass.states.get("climate.thermostat").state == "cool"

    climate.state = 5
    await find_update_callback(mock_niko_home_control_connection, 5)(5)
    assert hass.states.get("climate.thermostat").state == "auto"
    assert hass.states.get("climate.thermostat").attributes["preset_mode"] == "prog1"

    climate.state = 6
    await find_update_callback(mock_niko_home_control_connection, 5)(6)
    assert hass.states.get("climate.thermostat").state == "auto"
    assert hass.states.get("climate.thermostat").attributes["preset_mode"] == "prog2"

    climate.state = 7
    await find_update_callback(mock_niko_home_control_connection, 5)(7)
    assert hass.states.get("climate.thermostat").state == "auto"
    assert hass.states.get("climate.thermostat").attributes["preset_mode"] == "prog3"
