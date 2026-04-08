"""Test Lutron device triggers."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.device_automation import (
    DeviceAutomationType,
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.lutron import DOMAIN, device_trigger
from homeassistant.const import Platform
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry, async_get_device_automations


@pytest.fixture(autouse=True)
def setup_platforms():
    """Patch PLATFORMS for all tests in this file."""
    with patch("homeassistant.components.lutron.PLATFORMS", [Platform.EVENT]):
        yield


async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_lutron: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test keypad triggers are exposed through device automations."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        identifiers={
            (DOMAIN, f"{mock_lutron.guid}_{mock_lutron.areas[0].keypads[0].uuid}")
        }
    )
    assert device is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert triggers == [
        {
            "device_id": device.id,
            "domain": DOMAIN,
            "platform": "device",
            "type": "single_press",
            "subtype": "button_1",
            "metadata": {},
        }
    ]


async def test_trigger_fires_on_event(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_lutron: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device trigger fires from lutron button events."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    keypad = mock_lutron.areas[0].keypads[0]
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{mock_lutron.guid}_{keypad.uuid}")}
    )
    assert device is not None

    result: list[dict[str, Any]] = []

    @callback
    def trigger_callback(
        run_variables: dict[str, Any], context: Context | None = None
    ) -> None:
        result.append(run_variables)

    await device_trigger.async_attach_trigger(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "single_press",
            "subtype": "button_1",
        },
        trigger_callback,
        {"trigger_data": {}, "variables": {}},
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        "lutron_event",
        {
            "action": "single",
            "button_subtype": "button_1",
            "keypad_uuid": keypad.uuid,
        },
    )
    await hass.async_block_till_done()

    assert len(result) == 1
    trigger_data = result[0]["trigger"]["event"].data
    assert trigger_data["action"] == "single"
    assert trigger_data["button_subtype"] == "button_1"
    assert trigger_data["keypad_uuid"] == keypad.uuid


async def test_invalid_trigger_raises(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_lutron: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test invalid button subtype is rejected."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        identifiers={
            (DOMAIN, f"{mock_lutron.guid}_{mock_lutron.areas[0].keypads[0].uuid}")
        }
    )
    assert device is not None

    with pytest.raises(InvalidDeviceAutomationConfig):
        await device_trigger.async_validate_trigger_config(
            hass,
            {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": device.id,
                "type": "single_press",
                "subtype": "button_99",
            },
        )


async def test_pico_get_triggers_use_semantic_subtypes(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_lutron: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Pico triggers use semantic subtypes in device automations."""
    keypad = mock_lutron.areas[0].keypads[0]
    keypad.type = "PICO_KEYPAD"

    button = keypad.buttons[0]
    button.number = 2

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{mock_lutron.guid}_{keypad.uuid}")}
    )
    assert device is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert triggers == [
        {
            "device_id": device.id,
            "domain": DOMAIN,
            "platform": "device",
            "type": "single_press",
            "subtype": "top",
            "metadata": {},
        }
    ]


async def test_pico_trigger_fires_on_semantic_subtype(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_lutron: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Pico device triggers match semantic button subtypes."""
    keypad = mock_lutron.areas[0].keypads[0]
    keypad.type = "PICO_KEYPAD"

    button = keypad.buttons[0]
    button.number = 5
    button.button_type = "SingleSceneRaiseLower"

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{mock_lutron.guid}_{keypad.uuid}")}
    )
    assert device is not None

    result: list[dict[str, Any]] = []

    @callback
    def trigger_callback(
        run_variables: dict[str, Any], context: Context | None = None
    ) -> None:
        result.append(run_variables)

    await device_trigger.async_attach_trigger(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "press",
            "subtype": "raise",
        },
        trigger_callback,
        {"trigger_data": {}, "variables": {}},
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        "lutron_event",
        {
            "action": "pressed",
            "button_subtype": "raise",
            "keypad_uuid": keypad.uuid,
        },
    )
    await hass.async_block_till_done()

    assert len(result) == 1
    trigger_data = result[0]["trigger"]["event"].data
    assert trigger_data["action"] == "pressed"
    assert trigger_data["button_subtype"] == "raise"
    assert trigger_data["keypad_uuid"] == keypad.uuid
