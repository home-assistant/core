"""Test the Flic Button device triggers."""

from unittest.mock import patch

from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.flic_button.const import (
    CONF_BATTERY_LEVEL,
    CONF_DEVICE_TYPE,
    CONF_PAIRING_ID,
    CONF_PAIRING_KEY,
    CONF_SERIAL_NUMBER,
    CONF_SIG_BITS,
    DOMAIN,
    DeviceType,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

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

from tests.common import MockConfigEntry, async_get_device_automations


async def _setup_entry(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    address: str,
    serial_number: str,
    device_type: DeviceType,
    is_duo: bool = False,
    is_twist: bool = False,
) -> None:
    """Set up a config entry with a mock coordinator."""
    entry.add_to_hass(hass)

    mock_coordinator = create_mock_coordinator(
        address=address,
        serial_number=serial_number,
        device_type=device_type,
        is_duo=is_duo,
        is_twist=is_twist,
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


async def test_flic2_device_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test Flic 2 device triggers include base button events."""
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

    await _setup_entry(hass, entry, FLIC2_ADDRESS, FLIC2_SERIAL, DeviceType.FLIC2)

    device = device_registry.async_get_device(identifiers={(DOMAIN, FLIC2_ADDRESS)})
    assert device is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    trigger_types = {t["type"] for t in triggers}

    assert "click" in trigger_types
    assert "double_click" in trigger_types
    assert "hold" in trigger_types
    assert "up" in trigger_types
    assert "down" in trigger_types


async def test_duo_device_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test Flic Duo device triggers include swipe and rotation events."""
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

    await _setup_entry(
        hass, entry, DUO_ADDRESS, DUO_SERIAL, DeviceType.DUO, is_duo=True
    )

    device = device_registry.async_get_device(identifiers={(DOMAIN, DUO_ADDRESS)})
    assert device is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    trigger_types = {t["type"] for t in triggers}
    trigger_subtypes = {t["subtype"] for t in triggers}

    # Should have both button subtypes
    assert "big_button" in trigger_subtypes
    assert "small_button" in trigger_subtypes

    # Should have swipe and rotation events
    assert "swipe_left" in trigger_types
    assert "swipe_right" in trigger_types
    assert "rotate_clockwise" in trigger_types


async def test_twist_device_triggers_default_mode(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test Flic Twist DEFAULT mode triggers include increment/decrement."""
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

    await _setup_entry(
        hass, entry, TWIST_ADDRESS, TWIST_SERIAL, DeviceType.TWIST, is_twist=True
    )

    device = device_registry.async_get_device(identifiers={(DOMAIN, TWIST_ADDRESS)})
    assert device is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    trigger_types = {t["type"] for t in triggers}

    assert "twist_increment" in trigger_types
    assert "twist_decrement" in trigger_types
    assert "click" in trigger_types
