"""Test the Flic Button event platform."""

from unittest.mock import patch

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
    create_mock_coordinator,
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

    mock_coordinator = create_mock_coordinator(
        FLIC2_ADDRESS, FLIC2_SERIAL, DeviceType.FLIC2
    )

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
        ),
        patch(
            "homeassistant.components.flic_button.FlicCoordinator",
            return_value=mock_coordinator,
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

    mock_coordinator = create_mock_coordinator(
        DUO_ADDRESS, DUO_SERIAL, DeviceType.DUO, is_duo=True
    )

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
        ),
        patch(
            "homeassistant.components.flic_button.FlicCoordinator",
            return_value=mock_coordinator,
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

    mock_coordinator = create_mock_coordinator(
        TWIST_ADDRESS, TWIST_SERIAL, DeviceType.TWIST, is_twist=True
    )

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
        ),
        patch(
            "homeassistant.components.flic_button.FlicCoordinator",
            return_value=mock_coordinator,
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

    mock_coordinator = create_mock_coordinator(
        TWIST_ADDRESS, TWIST_SERIAL, DeviceType.TWIST, is_twist=True
    )

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
        ),
        patch(
            "homeassistant.components.flic_button.FlicCoordinator",
            return_value=mock_coordinator,
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

    mock_coordinator = create_mock_coordinator(
        FLIC2_ADDRESS, FLIC2_SERIAL, DeviceType.FLIC2
    )
    # Device is disconnected
    mock_coordinator.connected = False

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
        ),
        patch(
            "homeassistant.components.flic_button.FlicCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
