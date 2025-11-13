"""Tests for the Niko Home Control Climate platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
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


@pytest.mark.parametrize(
    ("service", "service_parameters", "api_method", "api_parameters"),
    [
        ("set_temperature", {"temperature": 25}, "set_temperature", (25,)),
        ("set_preset_mode", {ATTR_PRESET_MODE: "eco"}, "set_mode", (2,)),
        ("set_hvac_mode", {ATTR_HVAC_MODE: HVACMode.COOL}, "set_mode", (4,)),
        ("set_hvac_mode", {ATTR_HVAC_MODE: HVACMode.OFF}, "set_mode", (3,)),
        ("set_hvac_mode", {ATTR_HVAC_MODE: HVACMode.AUTO}, "set_mode", (5,)),
    ],
)
async def test_set(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    climate: AsyncMock,
    service: str,
    service_parameters: dict[str, Any],
    api_method: str,
    api_parameters: tuple[Any, ...],
) -> None:
    """Test setting a value on the climate entity."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        "climate",
        service,
        {ATTR_ENTITY_ID: "climate.thermostat"} | service_parameters,
        blocking=True,
    )
    getattr(
        mock_niko_home_control_connection.thermostats["thermostat-5"],
        api_method,
    ).assert_called_once_with(*api_parameters)


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
