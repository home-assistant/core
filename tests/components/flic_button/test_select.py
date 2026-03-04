"""Test the Flic Button select platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.flic_button.const import (
    CONF_BATTERY_LEVEL,
    CONF_BUTTON_UUID,
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
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import (
    TEST_BATTERY_LEVEL,
    TEST_BUTTON_UUID,
    TEST_PAIRING_ID,
    TEST_PAIRING_KEY,
    TEST_SIG_BITS,
    TWIST_ADDRESS,
    TWIST_SERIAL,
    create_mock_coordinator,
)

from tests.common import MockConfigEntry


async def test_select_entity_created_in_selector_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test selected slot select entity is created in SELECTOR mode."""
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
            CONF_BUTTON_UUID: TEST_BUTTON_UUID.hex(),
        },
        options={CONF_PUSH_TWIST_MODE: PushTwistMode.SELECTOR},
    )
    entry.add_to_hass(hass)

    mock_coordinator = create_mock_coordinator(
        address=TWIST_ADDRESS,
        serial_number=TWIST_SERIAL,
        device_type=DeviceType.TWIST,
        is_twist=True,
    )
    mock_coordinator.get_slot_value = MagicMock(return_value=0.0)
    mock_coordinator.set_slot_value = MagicMock()

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch("homeassistant.components.flic_button.FlicClient"),
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

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    select_entities = [e for e in entities if e.domain == "select"]

    assert len(select_entities) == 1
    assert select_entities[0].translation_key == "selected_slot"


async def test_select_entity_not_created_in_default_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test selected slot select entity is NOT created in DEFAULT mode."""
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
        address=TWIST_ADDRESS,
        serial_number=TWIST_SERIAL,
        device_type=DeviceType.TWIST,
        is_twist=True,
    )

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch("homeassistant.components.flic_button.FlicClient"),
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

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    select_entities = [e for e in entities if e.domain == "select"]

    assert len(select_entities) == 0


async def test_select_entity_read_only(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the select entity raises on user selection."""
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
            CONF_BUTTON_UUID: TEST_BUTTON_UUID.hex(),
        },
        options={CONF_PUSH_TWIST_MODE: PushTwistMode.SELECTOR},
    )
    entry.add_to_hass(hass)

    mock_coordinator = create_mock_coordinator(
        address=TWIST_ADDRESS,
        serial_number=TWIST_SERIAL,
        device_type=DeviceType.TWIST,
        is_twist=True,
    )
    mock_coordinator.get_slot_value = MagicMock(return_value=0.0)
    mock_coordinator.set_slot_value = MagicMock()

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch("homeassistant.components.flic_button.FlicClient"),
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

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    select_entities = [e for e in entities if e.domain == "select"]
    assert len(select_entities) == 1

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": select_entities[0].entity_id, "option": "slot_2"},
            blocking=True,
        )
