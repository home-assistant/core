"""Tests for Broadlink buttons."""

from unittest.mock import patch

from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import get_device

IR_DEVICES = ["Entrance", "Living Room", "Office", "Garage"]
NON_IR_DEVICE = "Bedroom"
INFRARED_MODULE = "homeassistant.components.broadlink.infrared"


async def test_button_setup_works(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a capture button is created for every IR-capable device."""
    for device in map(get_device, IR_DEVICES):
        mock_setup = await device.setup_entry(hass)

        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, mock_setup.entry.unique_id)}
        )
        entries = er.async_entries_for_device(entity_registry, device_entry.id)
        buttons = [entry for entry in entries if entry.domain == Platform.BUTTON]

        assert len(buttons) == 1
        assert buttons[0].unique_id == f"{device.mac}-capture-ir-code"


async def test_button_not_created_for_non_ir_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no capture button is created for devices without IR."""
    device = get_device(NON_IR_DEVICE)
    mock_setup = await device.setup_entry(hass)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_setup.entry.entry_id
    )
    buttons = [entry for entry in entries if entry.domain == Platform.BUTTON]

    assert len(buttons) == 0


async def test_button_press_starts_capturing(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test pressing the button puts the device into learning mode."""
    device = get_device("Entrance")
    mock_setup = await device.setup_entry(hass)

    button_entity_id = entity_registry.async_get_entity_id(
        Platform.BUTTON, DOMAIN, f"{device.mac}-capture-ir-code"
    )
    assert button_entity_id
    assert mock_setup.api.enter_learning.call_count == 0

    with patch(f"{INFRARED_MODULE}.POLL_INTERVAL", 0):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: button_entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert mock_setup.api.enter_learning.call_count >= 1
