"""Tests for the Seko PoolDose number platform."""

from copy import deepcopy
from unittest.mock import AsyncMock

from pooldose.request_status import RequestStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.NUMBER]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_all_numbers(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Pooldose numbers."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_number_entity_unavailable_no_coordinator_data(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test number entity becomes unavailable when coordinator has no data."""
    # Verify entity has a state initially
    ph_target_state = hass.states.get("number.pool_device_ph_target")
    assert ph_target_state.state == "6.5"

    # Update coordinator data to None
    mock_pooldose_client.instant_values_structured.return_value = (None, None)
    coordinator = init_integration.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Check entity becomes unavailable
    ph_target_state = hass.states.get("number.pool_device_ph_target")
    assert ph_target_state.state == "unavailable"


@pytest.mark.usefixtures("init_integration")
async def test_number_state_changes(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test number state changes when coordinator updates."""
    # Initial state
    ph_target_state = hass.states.get("number.pool_device_ph_target")
    assert ph_target_state.state == "6.5"

    # Update coordinator data with number value changed
    current_data = mock_pooldose_client.instant_values_structured.return_value[1]
    updated_data = deepcopy(current_data)
    updated_data["number"]["ph_target"]["value"] = 7.2

    mock_pooldose_client.instant_values_structured.return_value = (
        RequestStatus.SUCCESS,
        updated_data,
    )

    coordinator = init_integration.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Check state changed
    ph_target_state = hass.states.get("number.pool_device_ph_target")
    assert ph_target_state.state == "7.2"


@pytest.mark.usefixtures("init_integration")
async def test_set_number_value(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test setting a number value."""
    # Verify initial state
    ph_target_state = hass.states.get("number.pool_device_ph_target")
    assert ph_target_state.state == "6.5"

    # Set new value
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.pool_device_ph_target", "value": 7.0},
        blocking=True,
    )

    # Verify API was called
    mock_pooldose_client.set_number.assert_called_once_with("ph_target", 7.0)

    # Verify state updated immediately (optimistic update)
    ph_target_state = hass.states.get("number.pool_device_ph_target")
    assert ph_target_state.state == "7.0"


@pytest.mark.usefixtures("init_integration")
async def test_number_attributes(
    hass: HomeAssistant,
) -> None:
    """Test number entity attributes (min, max, step)."""
    # Test pH target attributes
    ph_target_state = hass.states.get("number.pool_device_ph_target")
    assert ph_target_state.attributes["min"] == 6
    assert ph_target_state.attributes["max"] == 8
    assert ph_target_state.attributes["step"] == 0.1

    # Test ORP target attributes
    orp_target_state = hass.states.get("number.pool_device_orp_target")
    assert orp_target_state.attributes["min"] == 400
    assert orp_target_state.attributes["max"] == 850
    assert orp_target_state.attributes["step"] == 1

    # Test Chlorine target attributes
    cl_target_state = hass.states.get("number.pool_device_chlorine_target")
    assert cl_target_state.attributes["min"] == 0
    assert cl_target_state.attributes["max"] == 65535
    assert cl_target_state.attributes["step"] == 0.01
