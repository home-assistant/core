"""Test the Flic Button event platform."""

from unittest.mock import MagicMock

from pyflic_ble import DeviceType, PushTwistMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.flic_button.const import CONF_PUSH_TWIST_MODE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures(
    "mock_flic_client",
    "mock_no_ble_device_from_address",
    "mock_bluetooth_register_callback",
)
@pytest.mark.parametrize(
    "device_type", [DeviceType.FLIC2, DeviceType.DUO, DeviceType.TWIST]
)
async def test_event_entity_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test event entities are created for each device type."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures(
    "mock_flic_client",
    "mock_no_ble_device_from_address",
    "mock_bluetooth_register_callback",
)
@pytest.mark.parametrize("device_type", [DeviceType.TWIST])
async def test_twist_event_entity_selector_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Flic Twist SELECTOR mode event entity has rotate and selector events."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_PUSH_TWIST_MODE: PushTwistMode.SELECTOR},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures(
    "mock_no_ble_device_from_address", "mock_bluetooth_register_callback"
)
async def test_flic2_button_event_triggers_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_flic_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Flic 2 button click event triggers entity state update."""
    await setup_integration(hass, mock_config_entry)

    # The entity registers a button event callback during setup; fetch it from the mock
    entity_cb = mock_flic_client.register_button_event_callback.call_args[0][0]
    entity_cb("click", {})
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    event_entities = [e for e in entities if e.domain == "event"]
    state = hass.states.get(event_entities[0].entity_id)
    assert state is not None
    assert state.attributes.get("event_type") == "click"


@pytest.mark.usefixtures(
    "mock_no_ble_device_from_address", "mock_bluetooth_register_callback"
)
@pytest.mark.parametrize("device_type", [DeviceType.DUO])
async def test_duo_button_event_filters_by_index(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_flic_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Duo button events are filtered by button_index."""
    await setup_integration(hass, mock_config_entry)

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    event_entities = [e for e in entities if e.domain == "event"]
    assert len(event_entities) == 2

    entity_cbs = [
        call.args[0]
        for call in mock_flic_client.register_button_event_callback.call_args_list
    ]

    # Fire event for button_index 0 (big button)
    for cb in entity_cbs:
        cb("click", {"button_index": 0})
    await hass.async_block_till_done()

    big_entity = next(e for e in event_entities if e.unique_id.endswith("_big"))
    small_entity = next(e for e in event_entities if e.unique_id.endswith("_small"))

    big_state = hass.states.get(big_entity.entity_id)
    small_state = hass.states.get(small_entity.entity_id)

    assert big_state is not None
    assert big_state.attributes.get("event_type") == "click"
    assert small_state is not None
    assert small_state.attributes.get("event_type") is None


@pytest.mark.usefixtures(
    "mock_no_ble_device_from_address", "mock_bluetooth_register_callback"
)
@pytest.mark.parametrize("device_type", [DeviceType.TWIST])
async def test_twist_rotate_event_triggers_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_flic_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Flic Twist rotate event triggers entity state update."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_PUSH_TWIST_MODE: PushTwistMode.SELECTOR},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_rotate_cb = mock_flic_client.register_rotate_event_callback.call_args[0][0]
    entity_rotate_cb("rotate_clockwise", {"value": 5})
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    event_entities = [e for e in entities if e.domain == "event"]
    state = hass.states.get(event_entities[0].entity_id)
    assert state is not None
    assert state.attributes.get("event_type") == "rotate_clockwise"


@pytest.mark.usefixtures(
    "mock_no_ble_device_from_address", "mock_bluetooth_register_callback"
)
@pytest.mark.parametrize("device_type", [DeviceType.TWIST])
async def test_twist_rotate_event_filtered_by_event_types(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_flic_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Twist rotate events are filtered if not in entity's event_types."""
    # DEFAULT mode does NOT include rotate_clockwise
    await setup_integration(hass, mock_config_entry)

    entity_rotate_cb = mock_flic_client.register_rotate_event_callback.call_args[0][0]
    entity_rotate_cb("rotate_clockwise", {"value": 5})
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    event_entities = [e for e in entities if e.domain == "event"]
    state = hass.states.get(event_entities[0].entity_id)
    assert state is not None
    assert state.attributes.get("event_type") is None


@pytest.mark.usefixtures(
    "mock_no_ble_device_from_address", "mock_bluetooth_register_callback"
)
@pytest.mark.parametrize("device_type", [DeviceType.DUO])
async def test_duo_rotate_event_filters_by_button_index(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_flic_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Duo rotate events are filtered by button_index."""
    await setup_integration(hass, mock_config_entry)

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    event_entities = [e for e in entities if e.domain == "event"]
    assert len(event_entities) == 2

    entity_rotate_cbs = [
        call.args[0]
        for call in mock_flic_client.register_rotate_event_callback.call_args_list
    ]
    for cb in entity_rotate_cbs:
        cb("rotate_clockwise", {"button_index": 1, "value": 3})
    await hass.async_block_till_done()

    big_entity = next(e for e in event_entities if e.unique_id.endswith("_big"))
    small_entity = next(e for e in event_entities if e.unique_id.endswith("_small"))

    big_state = hass.states.get(big_entity.entity_id)
    small_state = hass.states.get(small_entity.entity_id)

    assert big_state is not None
    assert big_state.attributes.get("event_type") is None
    assert small_state is not None
    assert small_state.attributes.get("event_type") == "rotate_clockwise"


@pytest.mark.usefixtures(
    "mock_no_ble_device_from_address", "mock_bluetooth_register_callback"
)
async def test_entity_availability_transitions(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_flic_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entity availability changes when connection state changes."""
    await setup_integration(hass, mock_config_entry)

    state_callbacks = [
        call.args[0] for call in mock_flic_client.register_state_callback.call_args_list
    ]

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    event_entities = [e for e in entities if e.domain == "event"]
    entity_id = event_entities[0].entity_id

    # Initially connected -> available
    assert hass.states.get(entity_id).state != "unavailable"

    # Simulate disconnection
    mock_flic_client.state.connected = False
    for cb in state_callbacks:
        cb(mock_flic_client.state)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unavailable"

    # Simulate reconnection
    mock_flic_client.state.connected = True
    for cb in state_callbacks:
        cb(mock_flic_client.state)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state != "unavailable"
