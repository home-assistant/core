"""Tests for the Seko PoolDose switch platform."""

from unittest.mock import AsyncMock

from pooldose.request_status import RequestStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SWITCH]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_all_switches(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Pooldose switches."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_switches_created(
    hass: HomeAssistant,
) -> None:
    """Test that switch entities are created."""
    # Verify all three switches exist
    assert hass.states.get("switch.pool_device_pause_dosing") is not None
    assert hass.states.get("switch.pool_device_pump_monitoring") is not None
    assert hass.states.get("switch.pool_device_frequency_input") is not None


@pytest.mark.usefixtures("init_integration")
async def test_switch_entity_unavailable_no_coordinator_data(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test switch entity becomes unavailable when coordinator has no data."""
    # Verify entity has a state initially
    pause_dosing_state = hass.states.get("switch.pool_device_pause_dosing")
    assert pause_dosing_state.state == STATE_OFF

    # Update coordinator data to None
    mock_pooldose_client.instant_values_structured.return_value = (None, None)
    coordinator = init_integration.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Check entity becomes unavailable
    pause_dosing_state = hass.states.get("switch.pool_device_pause_dosing")
    assert pause_dosing_state.state == "unavailable"


@pytest.mark.usefixtures("init_integration")
async def test_switch_state_changes(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test switch state changes when coordinator updates."""
    # Initial state
    pause_dosing_state = hass.states.get("switch.pool_device_pause_dosing")
    assert pause_dosing_state.state == STATE_OFF

    # Update coordinator data with switch value changed
    current_data = mock_pooldose_client.instant_values_structured.return_value[1]
    updated_data = current_data.copy()
    updated_data["switch"]["pause_dosing"]["value"] = True

    mock_pooldose_client.instant_values_structured.return_value = (
        RequestStatus.SUCCESS,
        updated_data,
    )

    coordinator = init_integration.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Check state changed
    pause_dosing_state = hass.states.get("switch.pool_device_pause_dosing")
    assert pause_dosing_state.state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_switch(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test turning on a switch."""
    # Verify initial state is off
    pause_dosing_state = hass.states.get("switch.pool_device_pause_dosing")
    assert pause_dosing_state.state == STATE_OFF

    # Turn on the switch
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: "switch.pool_device_pause_dosing"},
        blocking=True,
    )

    # Verify API was called
    mock_pooldose_client.set_switch.assert_called_once_with("pause_dosing", True)

    # Verify state updated immediately
    pause_dosing_state = hass.states.get("switch.pool_device_pause_dosing")
    assert pause_dosing_state.state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_turn_off_switch(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test turning off a switch."""
    # pump_monitoring starts as on in fixture data
    pump_monitoring_state = hass.states.get("switch.pool_device_pump_monitoring")
    assert pump_monitoring_state.state == STATE_ON

    # Turn off the switch
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: "switch.pool_device_pump_monitoring"},
        blocking=True,
    )

    # Verify API was called
    mock_pooldose_client.set_switch.assert_called_once_with("pump_monitoring", False)

    # Verify state updated immediately
    pump_monitoring_state = hass.states.get("switch.pool_device_pump_monitoring")
    assert pump_monitoring_state.state == STATE_OFF
