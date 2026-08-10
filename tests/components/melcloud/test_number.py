"""Test the MELCloud number platform."""

from unittest.mock import MagicMock

from aiohttp import ClientError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_platform

from tests.common import MockConfigEntry, snapshot_platform

FLOW_TEMPERATURE_ENTITY = "number.ecodan_zone_1_flow_temperature"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_get_devices")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all number entities with snapshot."""
    await setup_platform(hass, mock_config_entry, [Platform.NUMBER])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_get_devices")
async def test_set_flow_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atw_device: MagicMock,
) -> None:
    """Setting the value calls the library setter."""
    await setup_platform(hass, mock_config_entry, [Platform.NUMBER])
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: FLOW_TEMPERATURE_ENTITY, ATTR_VALUE: 45},
        blocking=True,
    )
    mock_atw_device.zones[0].set_target_flow_temperature.assert_awaited_once_with(45.0)


@pytest.mark.usefixtures("mock_get_devices")
async def test_set_flow_temperature_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atw_device: MagicMock,
) -> None:
    """A failed set surfaces as a HomeAssistantError."""
    mock_atw_device.zones[0].set_target_flow_temperature.side_effect = ClientError
    await setup_platform(hass, mock_config_entry, [Platform.NUMBER])
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: FLOW_TEMPERATURE_ENTITY, ATTR_VALUE: 45},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("operation_mode", "is_available"),
    [
        ("heat-flow", True),
        ("cool-flow", True),
        ("heat-thermostat", False),
        ("curve", False),
    ],
)
@pytest.mark.usefixtures("mock_get_devices")
async def test_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atw_device: MagicMock,
    operation_mode: str,
    is_available: bool,
) -> None:
    """The flow temperature is only available while a flow mode is selected."""
    mock_atw_device.zones[0].operation_mode = operation_mode
    await setup_platform(hass, mock_config_entry, [Platform.NUMBER])
    state = hass.states.get(FLOW_TEMPERATURE_ENTITY)
    assert state is not None
    assert (state.state != STATE_UNAVAILABLE) is is_available


@pytest.mark.parametrize(
    ("operation_mode", "expected_min", "expected_max"),
    [
        ("heat-flow", 25, 60),
        ("cool-flow", 5, 25),
    ],
)
@pytest.mark.usefixtures("mock_get_devices")
async def test_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atw_device: MagicMock,
    operation_mode: str,
    expected_min: int,
    expected_max: int,
) -> None:
    """The settable range follows the heating/cooling direction."""
    mock_atw_device.zones[0].operation_mode = operation_mode
    await setup_platform(hass, mock_config_entry, [Platform.NUMBER])
    state = hass.states.get(FLOW_TEMPERATURE_ENTITY)
    assert state is not None
    assert state.attributes["min"] == expected_min
    assert state.attributes["max"] == expected_max
