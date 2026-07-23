"""Test the MELCloud climate platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform

from tests.common import MockConfigEntry, snapshot_platform

ZONE_CLIMATE_ENTITY = "climate.ecodan_zone_1"

HEAT_COOL_MODES = [
    "heat-thermostat",
    "heat-flow",
    "curve",
    "cool-thermostat",
    "cool-flow",
]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_get_devices")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all climate entities with snapshot."""
    await setup_platform(hass, mock_config_entry, [Platform.CLIMATE])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_get_devices")
async def test_hvac_modes_heat_only(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A heat-only zone exposes only OFF and HEAT."""
    await setup_platform(hass, mock_config_entry, [Platform.CLIMATE])
    state = hass.states.get(ZONE_CLIMATE_ENTITY)
    assert state is not None
    assert state.attributes["hvac_modes"] == [HVACMode.OFF, HVACMode.HEAT]


@pytest.mark.usefixtures("mock_get_devices")
async def test_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atw_device: MagicMock,
) -> None:
    """Turning off powers the device down."""
    await setup_platform(hass, mock_config_entry, [Platform.CLIMATE])
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ZONE_CLIMATE_ENTITY},
        blocking=True,
    )
    mock_atw_device.set.assert_awaited_with({"power": False})


@pytest.mark.usefixtures("mock_get_devices")
async def test_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atw_device: MagicMock,
) -> None:
    """Turning on powers the device up."""
    await setup_platform(hass, mock_config_entry, [Platform.CLIMATE])
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ZONE_CLIMATE_ENTITY},
        blocking=True,
    )
    mock_atw_device.set.assert_awaited_with({"power": True})


@pytest.mark.usefixtures("mock_get_devices")
async def test_set_hvac_mode_heat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atw_device: MagicMock,
) -> None:
    """Setting hvac_mode HEAT keeps the current control method."""
    await setup_platform(hass, mock_config_entry, [Platform.CLIMATE])
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ZONE_CLIMATE_ENTITY, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    mock_atw_device.zones[0].set_operation_mode.assert_awaited_once_with("heat-flow")
    mock_atw_device.set.assert_not_called()


@pytest.mark.parametrize(
    ("current_mode", "hvac_mode", "expected_mode"),
    [
        ("heat-flow", HVACMode.COOL, "cool-flow"),
        ("heat-thermostat", HVACMode.COOL, "cool-thermostat"),
        ("curve", HVACMode.COOL, "cool-thermostat"),
        ("cool-flow", HVACMode.HEAT, "heat-flow"),
        ("cool-thermostat", HVACMode.HEAT, "heat-thermostat"),
    ],
)
@pytest.mark.usefixtures("mock_get_devices")
async def test_set_hvac_mode_preserves_method(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atw_device: MagicMock,
    current_mode: str,
    hvac_mode: HVACMode,
    expected_mode: str,
) -> None:
    """Switching direction preserves the flow/thermostat method where possible."""
    zone = mock_atw_device.zones[0]
    zone.operation_modes = HEAT_COOL_MODES
    zone.operation_mode = current_mode
    await setup_platform(hass, mock_config_entry, [Platform.CLIMATE])
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ZONE_CLIMATE_ENTITY, "hvac_mode": hvac_mode},
        blocking=True,
    )
    zone.set_operation_mode.assert_awaited_once_with(expected_mode)
    mock_atw_device.set.assert_not_called()


@pytest.mark.usefixtures("mock_get_devices")
async def test_set_hvac_mode_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atw_device: MagicMock,
) -> None:
    """Setting hvac_mode OFF powers the device down."""
    await setup_platform(hass, mock_config_entry, [Platform.CLIMATE])
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ZONE_CLIMATE_ENTITY, "hvac_mode": HVACMode.OFF},
        blocking=True,
    )
    mock_atw_device.set.assert_awaited_with({"power": False})


@pytest.mark.usefixtures("mock_get_devices")
async def test_set_hvac_mode_powers_on_when_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atw_device: MagicMock,
) -> None:
    """Setting a direction while powered off also powers on."""
    mock_atw_device.power = False
    await setup_platform(hass, mock_config_entry, [Platform.CLIMATE])
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ZONE_CLIMATE_ENTITY, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    mock_atw_device.zones[0].set_operation_mode.assert_awaited_once_with("heat-flow")
    mock_atw_device.set.assert_awaited_with({"power": True})
