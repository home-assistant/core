"""The tests for Philips Hue device triggers for V2 bridge."""

from typing import Any
from unittest.mock import Mock, patch

from aiohue.v2.models.button import ButtonEvent
import pytest
from pytest_unordered import unordered

from homeassistant.components import automation, hue
from homeassistant.components.device_automation import (
    DeviceAutomationType,
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.hue import device_trigger
from homeassistant.components.hue.v2.device import async_setup_devices
from homeassistant.components.hue.v2.hue_event import async_setup_hue_events
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
    SERVICE_TURN_OFF,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.trigger import TriggerInfo
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonArrayType

from .conftest import create_config_entry, setup_platform

from tests.common import (
    MockConfigEntry,
    async_capture_events,
    async_get_device_automations,
)

WALL_SWITCH_DEVICE_ID = "3ff06175-29e8-44a8-8fe7-af591b0025da"
WALL_SWITCH_BUTTON_PRESS = {
    "button": {
        "button_report": {
            "event": "initial_press",
            "updated": "2021-10-01T12:00:00Z",
        }
    },
    "id": "c658d3d8-a013-4b81-8ac6-78b248537e70",
    "metadata": {"control_id": 1},
    "type": "button",
}


async def test_hue_event(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test hue button events."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(
        hass, mock_bridge_v2, [Platform.BINARY_SENSOR, Platform.SENSOR]
    )
    await async_setup_devices(mock_bridge_v2)
    await async_setup_hue_events(mock_bridge_v2)

    events = async_capture_events(hass, "hue_event")

    # Emit button update event
    btn_event = {
        "button": {
            "button_report": {
                "event": "initial_press",
                "updated": "2021-10-01T12:00:00Z",
            }
        },
        "id": "c658d3d8-a013-4b81-8ac6-78b248537e70",
        "metadata": {"control_id": 1},
        "type": "button",
    }
    mock_bridge_v2.api.emit_event("update", btn_event)

    # wait for the event
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["id"] == "wall_switch_with_2_controls_button"
    assert events[0].data["unique_id"] == btn_event["id"]
    assert events[0].data["type"] == btn_event["button"]["button_report"]["event"]
    assert events[0].data["subtype"] == btn_event["metadata"]["control_id"]


async def test_get_triggers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test we get the expected triggers from a hue remote."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(
        hass, mock_bridge_v2, [Platform.BINARY_SENSOR, Platform.SENSOR]
    )

    # Get triggers for `Wall switch with 2 controls`
    hue_wall_switch_device = device_registry.async_get_device_by_identifier(
        (hue.DOMAIN, "3ff06175-29e8-44a8-8fe7-af591b0025da"),
        mock_bridge_v2.config_entry.entry_id,
    )
    # The device is linked to the bridge device as its via_device.
    bridge_device = device_registry.async_get_device_by_identifier(
        (hue.DOMAIN, mock_bridge_v2.api.config.bridge_id),
        mock_bridge_v2.config_entry.entry_id,
    )
    assert hue_wall_switch_device.via_device_id == bridge_device.id
    hue_bat_sensor = entity_registry.async_get(
        "sensor.wall_switch_with_2_controls_battery"
    )
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, hue_wall_switch_device.id
    )

    trigger_batt = {
        "platform": "device",
        "domain": "sensor",
        "device_id": hue_wall_switch_device.id,
        "type": "battery_level",
        "entity_id": hue_bat_sensor.id,
        "metadata": {"secondary": True},
    }

    expected_triggers = [
        trigger_batt,
        *(
            {
                "platform": "device",
                "domain": hue.DOMAIN,
                "device_id": hue_wall_switch_device.id,
                "unique_id": resource_id,
                "type": event_type.value,
                "subtype": control_id,
                "metadata": {},
            }
            for event_type in (
                ButtonEvent.INITIAL_PRESS,
                ButtonEvent.LONG_RELEASE,
                ButtonEvent.REPEAT,
                ButtonEvent.LONG_PRESS,
                ButtonEvent.SHORT_RELEASE,
            )
            for control_id, resource_id in (
                (1, "c658d3d8-a013-4b81-8ac6-78b248537e70"),
                (2, "be1eb834-bdf5-4d26-8fba-7b1feaa83a9d"),
            )
        ),
    ]

    assert triggers == unordered(expected_triggers)


async def test_get_triggers_for_removed_device(
    hass: HomeAssistant,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test triggers for a device removed from the bridge.

    Regression test for https://github.com/home-assistant/core/issues/152937
    """
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(
        hass, mock_bridge_v2, [Platform.BINARY_SENSOR, Platform.SENSOR]
    )

    # Create a device entry with a Hue ID that doesn't exist on the bridge
    orphaned_device = device_registry.async_get_or_create(
        config_entry_id=mock_bridge_v2.config_entry.entry_id,
        identifiers={(hue.DOMAIN, "non-existent-hue-device-id")},
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, orphaned_device.id
    )
    assert triggers == []


async def test_if_fires_when_config_entry_loads_late(
    hass: HomeAssistant,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test a trigger attached before the bridge is loaded still fires.

    Regression test for https://github.com/home-assistant/core/issues/156390
    """
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    config_entry = create_config_entry(api_version=2)
    config_entry.add_to_hass(hass)

    # the device is restored from the registry while the bridge is still setting up
    wall_switch_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(hue.DOMAIN, WALL_SWITCH_DEVICE_ID)},
    )

    assert await async_setup_component(
        hass, automation.DOMAIN, _automation_config(wall_switch_device.id)
    )
    await hass.async_block_till_done()
    assert config_entry.state is not ConfigEntryState.LOADED

    await _load_bridge(hass, mock_bridge_v2, config_entry)

    mock_bridge_v2.api.emit_event("update", WALL_SWITCH_BUTTON_PRESS)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == ButtonEvent.INITIAL_PRESS.value

    # turning the automation off detaches the trigger again
    await _turn_off_automation(hass)
    service_calls.clear()
    mock_bridge_v2.api.emit_event("update", WALL_SWITCH_BUTTON_PRESS)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert len(service_calls) == 0


async def test_trigger_removed_before_config_entry_loads(
    hass: HomeAssistant,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test a trigger removed while the bridge is still loading never fires."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    config_entry = create_config_entry(api_version=2)
    config_entry.add_to_hass(hass)
    wall_switch_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(hue.DOMAIN, WALL_SWITCH_DEVICE_ID)},
    )

    assert await async_setup_component(
        hass, automation.DOMAIN, _automation_config(wall_switch_device.id)
    )
    await hass.async_block_till_done()

    await _turn_off_automation(hass)
    service_calls.clear()

    await _load_bridge(hass, mock_bridge_v2, config_entry)

    mock_bridge_v2.api.emit_event("update", WALL_SWITCH_BUTTON_PRESS)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert len(service_calls) == 0


async def test_attach_trigger_for_device_without_hue_bridge(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test attaching a trigger for a device that is not on any Hue bridge."""
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other", "not-a-hue-device")},
    )
    trigger_info: TriggerInfo = {
        "domain": automation.DOMAIN,
        "name": "test",
        "variables": None,
        "trigger_data": {"id": "", "idx": "0", "alias": None},
    }

    with pytest.raises(InvalidDeviceAutomationConfig):
        await device_trigger.async_attach_trigger(
            hass,
            {
                CONF_PLATFORM: "device",
                CONF_DOMAIN: hue.DOMAIN,
                CONF_DEVICE_ID: device.id,
                CONF_TYPE: ButtonEvent.INITIAL_PRESS.value,
                "subtype": 1,
            },
            Mock(),
            trigger_info,
        )


def _automation_config(device_id: str) -> dict[str, Any]:
    """Return an automation config triggering on a button press of the device."""
    return {
        automation.DOMAIN: [
            {
                "trigger": {
                    "platform": "device",
                    "domain": hue.DOMAIN,
                    "device_id": device_id,
                    "type": ButtonEvent.INITIAL_PRESS.value,
                    "subtype": 1,
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {"some": "{{ trigger.event.data.type }}"},
                },
            }
        ]
    }


async def _load_bridge(
    hass: HomeAssistant, mock_bridge: Mock, config_entry: MockConfigEntry
) -> None:
    """Set up a config entry that was already added to hass."""
    mock_bridge.config_entry = config_entry
    with (
        patch.object(hue.migration, "is_v2_bridge", return_value=True),
        patch("homeassistant.components.hue.HueBridge", return_value=mock_bridge),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED
    await async_setup_hue_events(mock_bridge)
    await hass.async_block_till_done()


async def _turn_off_automation(hass: HomeAssistant) -> None:
    """Turn off the automation created by `_automation_config`."""
    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "automation.automation_0"},
        blocking=True,
    )
    await hass.async_block_till_done()
