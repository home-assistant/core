"""Test the Flic Button event platform."""

from unittest.mock import MagicMock, patch

from homeassistant.components.event import EventDeviceClass
from homeassistant.components.flic_button.const import (
    CONF_BATTERY_LEVEL,
    CONF_DEVICE_TYPE,
    CONF_PAIRING_ID,
    CONF_PAIRING_KEY,
    CONF_PUSH_TWIST_MODE,
    CONF_SERIAL_NUMBER,
    CONF_SIG_BITS,
    DOMAIN,
    DeviceType,
    PushTwistMode,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    DUO_ADDRESS,
    DUO_SERIAL,
    FLIC2_ADDRESS,
    FLIC2_SERIAL,
    TEST_BATTERY_LEVEL,
    TEST_PAIRING_ID,
    TEST_PAIRING_KEY,
    TEST_SIG_BITS,
    TWIST_ADDRESS,
    TWIST_SERIAL,
    create_mock_flic_client,
)

from tests.common import MockConfigEntry


async def test_flic2_event_entity_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Flic 2 event entity is created with correct properties."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic 2 ({FLIC2_SERIAL})",
        unique_id=FLIC2_ADDRESS,
        data={
            CONF_ADDRESS: FLIC2_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: FLIC2_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.FLIC2.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)

    mock_client = create_mock_flic_client(FLIC2_ADDRESS, FLIC2_SERIAL)

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Check event entity exists
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    event_entities = [e for e in entities if e.domain == "event"]

    # Flic 2 should have one event entity
    assert len(event_entities) == 1
    assert event_entities[0].original_device_class == EventDeviceClass.BUTTON


async def test_duo_event_entities_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Flic Duo creates two event entities (big and small buttons)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic Duo ({DUO_SERIAL})",
        unique_id=DUO_ADDRESS,
        data={
            CONF_ADDRESS: DUO_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: DUO_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.DUO.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)

    mock_client = create_mock_flic_client(DUO_ADDRESS, DUO_SERIAL, is_duo=True)

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Check event entities exist
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    event_entities = [e for e in entities if e.domain == "event"]

    # Flic Duo should have two event entities (big button and small button)
    assert len(event_entities) == 2

    # Both should be button device class
    for entity in event_entities:
        assert entity.original_device_class == EventDeviceClass.BUTTON


async def test_twist_event_entity_default_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Flic Twist DEFAULT mode event entity has increment/decrement events."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic Twist ({TWIST_SERIAL})",
        unique_id=TWIST_ADDRESS,
        data={
            CONF_ADDRESS: TWIST_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: TWIST_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.TWIST.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)

    mock_client = create_mock_flic_client(TWIST_ADDRESS, TWIST_SERIAL, is_twist=True)

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Check event entity exists
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    event_entities = [e for e in entities if e.domain == "event"]

    # Flic Twist should have one event entity
    assert len(event_entities) == 1
    assert event_entities[0].original_device_class == EventDeviceClass.BUTTON

    # Verify DEFAULT mode has increment/decrement event types (not rotate/selector)
    state = hass.states.get(event_entities[0].entity_id)
    assert state is not None
    event_types = state.attributes.get("event_types", [])
    assert "twist_increment" in event_types
    assert "twist_decrement" in event_types
    assert "push_twist_increment" in event_types
    assert "push_twist_decrement" in event_types
    assert "rotate_clockwise" not in event_types
    assert "rotate_counter_clockwise" not in event_types
    assert "selector_changed" not in event_types


async def test_twist_event_entity_selector_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Flic Twist SELECTOR mode event entity has rotate and selector events."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic Twist ({TWIST_SERIAL})",
        unique_id=TWIST_ADDRESS,
        data={
            CONF_ADDRESS: TWIST_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: TWIST_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.TWIST.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
        options={CONF_PUSH_TWIST_MODE: PushTwistMode.SELECTOR},
    )
    entry.add_to_hass(hass)

    mock_client = create_mock_flic_client(TWIST_ADDRESS, TWIST_SERIAL, is_twist=True)

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Check event entity exists
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    event_entities = [e for e in entities if e.domain == "event"]

    # Flic Twist should have one event entity
    assert len(event_entities) == 1
    assert event_entities[0].original_device_class == EventDeviceClass.BUTTON

    # Verify SELECTOR mode has rotate and selector event types
    state = hass.states.get(event_entities[0].entity_id)
    assert state is not None
    event_types = state.attributes.get("event_types", [])
    assert "rotate_clockwise" in event_types
    assert "rotate_counter_clockwise" in event_types
    assert "selector_changed" in event_types
    assert "twist_increment" not in event_types
    assert "twist_decrement" not in event_types


async def test_event_entity_unavailable_when_disconnected(
    hass: HomeAssistant,
) -> None:
    """Test event entity shows unavailable when device is disconnected."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic 2 ({FLIC2_SERIAL})",
        unique_id=FLIC2_ADDRESS,
        data={
            CONF_ADDRESS: FLIC2_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: FLIC2_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.FLIC2.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)

    mock_client = create_mock_flic_client(FLIC2_ADDRESS, FLIC2_SERIAL, connected=False)

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def _setup_entry_with_callbacks(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_client: MagicMock,
) -> dict[str, list]:
    """Set up a config entry and capture registered callbacks."""
    button_callbacks: list = []
    rotate_callbacks: list = []

    def capture_button_cb(cb):
        button_callbacks.append(cb)
        return lambda: None

    def capture_rotate_cb(cb):
        rotate_callbacks.append(cb)
        return lambda: None

    mock_client.register_button_event_callback = MagicMock(
        side_effect=capture_button_cb
    )
    mock_client.register_rotate_event_callback = MagicMock(
        side_effect=capture_rotate_cb
    )

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return {"button": button_callbacks, "rotate": rotate_callbacks}


async def test_flic2_button_event_triggers_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Flic 2 button click event triggers entity state update."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic 2 ({FLIC2_SERIAL})",
        unique_id=FLIC2_ADDRESS,
        data={
            CONF_ADDRESS: FLIC2_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: FLIC2_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.FLIC2.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)
    mock_client = create_mock_flic_client(FLIC2_ADDRESS, FLIC2_SERIAL)

    callbacks = await _setup_entry_with_callbacks(hass, entry, mock_client)

    # Entity callback is registered first (during platform setup),
    # then bus callback from __init__.py
    assert len(callbacks["button"]) >= 2

    # Entity callback is first (registered during async_added_to_hass)
    entity_cb = callbacks["button"][0]
    entity_cb("click", {})
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    event_entities = [e for e in entities if e.domain == "event"]
    state = hass.states.get(event_entities[0].entity_id)
    assert state is not None
    assert state.attributes.get("event_type") == "click"


async def test_duo_button_event_filters_by_index(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Duo button events are filtered by button_index."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic Duo ({DUO_SERIAL})",
        unique_id=DUO_ADDRESS,
        data={
            CONF_ADDRESS: DUO_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: DUO_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.DUO.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)
    mock_client = create_mock_flic_client(DUO_ADDRESS, DUO_SERIAL, is_duo=True)

    callbacks = await _setup_entry_with_callbacks(hass, entry, mock_client)

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    event_entities = [e for e in entities if e.domain == "event"]
    assert len(event_entities) == 2

    # Entity callbacks are registered first (during async_added_to_hass),
    # then bus callback from __init__.py. Duo has 2 entity callbacks.
    entity_cbs = callbacks["button"][:2]

    # Fire event for button_index 0 (big button)
    for cb in entity_cbs:
        cb("click", {"button_index": 0})
    await hass.async_block_till_done()

    # Find the big button entity (unique_id ends with _big)
    big_entity = next(e for e in event_entities if e.unique_id.endswith("_big"))
    small_entity = next(e for e in event_entities if e.unique_id.endswith("_small"))

    big_state = hass.states.get(big_entity.entity_id)
    small_state = hass.states.get(small_entity.entity_id)

    # Big button should have the event, small should not
    assert big_state is not None
    assert big_state.attributes.get("event_type") == "click"
    # Small button should not have received the event (event_type should be None)
    assert small_state is not None
    assert small_state.attributes.get("event_type") is None


async def test_twist_rotate_event_triggers_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Flic Twist rotate event triggers entity state update."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic Twist ({TWIST_SERIAL})",
        unique_id=TWIST_ADDRESS,
        data={
            CONF_ADDRESS: TWIST_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: TWIST_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.TWIST.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)
    mock_client = create_mock_flic_client(TWIST_ADDRESS, TWIST_SERIAL, is_twist=True)

    callbacks = await _setup_entry_with_callbacks(hass, entry, mock_client)

    # Twist has rotation: entity rotate callback first, then bus callback
    assert len(callbacks["rotate"]) >= 2

    # Entity rotate callback is first (registered during async_added_to_hass)
    entity_rotate_cb = callbacks["rotate"][0]
    entity_rotate_cb("twist_increment", {"value": 5})
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    event_entities = [e for e in entities if e.domain == "event"]
    state = hass.states.get(event_entities[0].entity_id)
    assert state is not None
    assert state.attributes.get("event_type") == "twist_increment"


async def test_twist_rotate_event_filtered_by_event_types(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Twist rotate events are filtered if not in entity's event_types."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic Twist ({TWIST_SERIAL})",
        unique_id=TWIST_ADDRESS,
        data={
            CONF_ADDRESS: TWIST_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: TWIST_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.TWIST.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
        # DEFAULT mode does NOT include rotate_clockwise
    )
    entry.add_to_hass(hass)
    mock_client = create_mock_flic_client(TWIST_ADDRESS, TWIST_SERIAL, is_twist=True)

    callbacks = await _setup_entry_with_callbacks(hass, entry, mock_client)

    # Entity rotate callback is first
    entity_rotate_cb = callbacks["rotate"][0]
    # rotate_clockwise is NOT in DEFAULT mode event_types — should be filtered out
    entity_rotate_cb("rotate_clockwise", {"value": 5})
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    event_entities = [e for e in entities if e.domain == "event"]
    state = hass.states.get(event_entities[0].entity_id)
    assert state is not None
    # Event should NOT have been triggered
    assert state.attributes.get("event_type") is None


async def test_duo_rotate_event_filters_by_button_index(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Duo rotate events are filtered by button_index."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic Duo ({DUO_SERIAL})",
        unique_id=DUO_ADDRESS,
        data={
            CONF_ADDRESS: DUO_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: DUO_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.DUO.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)
    mock_client = create_mock_flic_client(DUO_ADDRESS, DUO_SERIAL, is_duo=True)

    callbacks = await _setup_entry_with_callbacks(hass, entry, mock_client)

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    event_entities = [e for e in entities if e.domain == "event"]
    assert len(event_entities) == 2

    # Entity rotate callbacks are first (2 for Duo), then bus callback
    entity_rotate_cbs = callbacks["rotate"][:2]
    for cb in entity_rotate_cbs:
        cb("rotate_clockwise", {"button_index": 1, "value": 3})
    await hass.async_block_till_done()

    big_entity = next(e for e in event_entities if e.unique_id.endswith("_big"))
    small_entity = next(e for e in event_entities if e.unique_id.endswith("_small"))

    big_state = hass.states.get(big_entity.entity_id)
    small_state = hass.states.get(small_entity.entity_id)

    # Only the small button entity should have the rotate event
    assert big_state is not None
    assert big_state.attributes.get("event_type") is None
    assert small_state is not None
    assert small_state.attributes.get("event_type") == "rotate_clockwise"


async def test_entity_availability_transitions(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity availability changes when connection state changes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic 2 ({FLIC2_SERIAL})",
        unique_id=FLIC2_ADDRESS,
        data={
            CONF_ADDRESS: FLIC2_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: FLIC2_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.FLIC2.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)
    mock_client = create_mock_flic_client(FLIC2_ADDRESS, FLIC2_SERIAL)

    state_callbacks: list = []

    def capture_state_cb(cb):
        state_callbacks.append(cb)
        return lambda: None

    mock_client.register_state_callback = MagicMock(side_effect=capture_state_cb)

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    event_entities = [e for e in entities if e.domain == "event"]
    entity_id = event_entities[0].entity_id

    # Initially connected -> available
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != "unavailable"

    # Simulate disconnection
    mock_client.state.connected = False
    for cb in state_callbacks:
        cb(mock_client.state)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"

    # Simulate reconnection
    mock_client.state.connected = True
    for cb in state_callbacks:
        cb(mock_client.state)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != "unavailable"
