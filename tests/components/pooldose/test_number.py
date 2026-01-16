"""Tests for the Seko PoolDose number platform."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pooldose.request_status import RequestStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


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
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test number entity becomes unavailable when coordinator has no data."""
    # Verify entity has a state initially
    ph_target_state = hass.states.get("number.pool_device_ph_target")
    assert ph_target_state.state == "6.5"

    # Update coordinator data to None
    mock_pooldose_client.instant_values_structured.return_value = (None, None)
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check entity becomes unavailable
    ph_target_state = hass.states.get("number.pool_device_ph_target")
    assert ph_target_state.state == "unavailable"


@pytest.mark.usefixtures("init_integration")
async def test_number_state_changes(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
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

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
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
async def test_actions_cannot_connect_number(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """When the client write method raises, ServiceValidationError('cannot_connect') is raised."""
    client = mock_pooldose_client
    entity_id = "number.pool_device_ph_target"
    before = hass.states.get(entity_id)
    assert before is not None

    client.is_connected = False
    client.set_number = AsyncMock(return_value=False)

    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            "number", "set_value", {"entity_id": entity_id, "value": 7.0}, blocking=True
        )

    assert excinfo.value.translation_key == "cannot_connect"

    after = hass.states.get(entity_id)
    assert after is not None
    assert before.state == after.state


@pytest.mark.usefixtures("init_integration")
async def test_actions_write_rejected_number(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """When the client write method returns False, ServiceValidationError('write_rejected') is raised."""
    client = mock_pooldose_client
    entity_id = "number.pool_device_ph_target"
    before = hass.states.get(entity_id)
    assert before is not None

    client.set_number = AsyncMock(return_value=False)

    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            "number", "set_value", {"entity_id": entity_id, "value": 7.0}, blocking=True
        )

    assert excinfo.value.translation_key == "write_rejected"

    after = hass.states.get(entity_id)
    assert after is not None
    assert before.state == after.state
