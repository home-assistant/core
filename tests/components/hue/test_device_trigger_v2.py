"""The tests for Philips Hue device triggers for V2 bridge."""

from unittest.mock import Mock, patch

from aiohue.v2.models.button import ButtonEvent
from pytest_unordered import unordered

from homeassistant.components import automation, hue
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.hue.v2.device import async_setup_devices
from homeassistant.components.hue.v2.hue_event import async_setup_hue_events
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonArrayType

from .conftest import create_config_entry, setup_platform

from tests.common import async_capture_events, async_get_device_automations


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
    hue_wall_switch_device = device_registry.async_get_device(
        identifiers={(hue.DOMAIN, "3ff06175-29e8-44a8-8fe7-af591b0025da")}
    )
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
        identifiers={(hue.DOMAIN, "3ff06175-29e8-44a8-8fe7-af591b0025da")},
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": hue.DOMAIN,
                        "device_id": wall_switch_device.id,
                        "type": ButtonEvent.INITIAL_PRESS.value,
                        "subtype": 1,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "{{ trigger.event.data.type }}"},
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert config_entry.state is not ConfigEntryState.LOADED

    mock_bridge_v2.config_entry = config_entry
    with (
        patch.object(hue.migration, "is_v2_bridge", return_value=True),
        patch("homeassistant.components.hue.HueBridge", return_value=mock_bridge_v2),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED
    await async_setup_hue_events(mock_bridge_v2)
    await hass.async_block_till_done()

    # Emit button update event
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "button": {
                "button_report": {
                    "event": "initial_press",
                    "updated": "2021-10-01T12:00:00Z",
                }
            },
            "id": "c658d3d8-a013-4b81-8ac6-78b248537e70",
            "metadata": {"control_id": 1},
            "type": "button",
        },
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == ButtonEvent.INITIAL_PRESS.value
