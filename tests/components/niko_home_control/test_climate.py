"""Tests for the Niko Home Control Light platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.climate import ATTR_HVAC_MODE, ATTR_PRESET_MODE
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


@pytest.mark.parametrize(
    ("thermostat_id", "entity_id", "temperature"), [(5, "climate.thermostat", 25)]
)
async def test_set_temperature(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    climate: AsyncMock,
    thermostat_id: int,
    entity_id: str,
    temperature: int,
) -> None:
    """Test setting a temperature."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: entity_id, "temperature": temperature},
        blocking=True,
    )
    mock_niko_home_control_connection.thermostats[
        f"thermostat-{thermostat_id}"
    ].set_temperature.assert_called_once_with(250.0)


@pytest.mark.parametrize(
    ("thermostat_id", "entity_id", "preset"), [(5, "climate.thermostat", "eco")]
)
async def test_set_preset(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    climate: AsyncMock,
    thermostat_id: int,
    entity_id: str,
    preset: str,
) -> None:
    """Test setting a preset."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: preset},
        blocking=True,
    )
    mock_niko_home_control_connection.thermostats[
        f"thermostat-{thermostat_id}"
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
        {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: "cool"},
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
        {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: "off"},
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
        {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: "auto"},
        blocking=True,
    )
    mock_niko_home_control_connection.thermostats[
        "thermostat-5"
    ].set_mode.assert_called_once_with(5)


async def test_is_expected_state(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on the light."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("climate.thermostat").state == "auto"


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
