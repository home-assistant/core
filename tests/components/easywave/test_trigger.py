"""Tests for Easywave purpose-specific triggers."""

from homeassistant.components import group
from homeassistant.components.easywave.const import (
    DOMAIN,
    EVENT_EASYWAVE,
    EVENT_TYPE_BUTTON_PRESS,
    EVENT_TYPE_BUTTON_RELEASE,
    EVENT_TYPE_GATEWAY_CONNECTED,
)
from homeassistant.components.group import DOMAIN as GROUP_DOMAIN
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_TRANSMITTER_DEVICE_ID,
    _entry_with_subentries,
    _transmitter_device_record,
    async_setup_easywave_entry,
)

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def _async_setup_entry(
    hass: HomeAssistant,
    *,
    button_count: int = 2,
) -> MockConfigEntry:
    """Set up an Easywave config entry with a group transmitter."""
    device = _transmitter_device_record(
        button_count=button_count,
        title="Test Transmitter",
    )
    entry = _entry_with_subentries(device)
    await async_setup_easywave_entry(hass, entry)
    return entry


async def test_easywave_button_press_a_trigger_fires(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Purpose-specific easywave.button_press_a trigger fires on matching events."""
    await _async_setup_entry(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)}
    )
    assert device is not None

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "trigger": "easywave.button_press_a",
                    "target": {"device_id": device.id},
                },
                "action": {
                    "service": "test.automation",
                    "data": {"subtype": "{{ trigger.event.data.subtype }}"},
                },
            }
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_EASYWAVE,
        {
            "device_id": device.id,
            "type": EVENT_TYPE_BUTTON_PRESS,
            "subtype": "a",
        },
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["subtype"] == "a"


async def test_easywave_button_press_a_trigger_fires_for_entity_target(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Purpose-specific trigger fires when configured via entity target selector."""
    await _async_setup_entry(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)}
    )
    assert device is not None
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_TRANSMITTER_DEVICE_ID}_last_button"
    )
    assert entity_id is not None

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "trigger": "easywave.button_press_a",
                    "target": {"entity_id": entity_id},
                },
                "action": {
                    "service": "test.automation",
                    "data": {"subtype": "{{ trigger.event.data.subtype }}"},
                },
            }
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_EASYWAVE,
        {
            "device_id": device.id,
            "type": EVENT_TYPE_BUTTON_PRESS,
            "subtype": "a",
        },
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["subtype"] == "a"


async def test_easywave_button_press_a_trigger_fires_for_area_target(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Purpose-specific trigger fires when configured via area target selector."""
    await _async_setup_entry(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)}
    )
    assert device is not None
    area = area_registry.async_get_or_create("living_room")
    device_registry.async_update_device(device.id, area_id=area.id)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "trigger": "easywave.button_press_a",
                    "target": {"area_id": area.id},
                },
                "action": {
                    "service": "test.automation",
                    "data": {"subtype": "{{ trigger.event.data.subtype }}"},
                },
            }
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_EASYWAVE,
        {
            "device_id": device.id,
            "type": EVENT_TYPE_BUTTON_PRESS,
            "subtype": "a",
        },
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["subtype"] == "a"


async def test_easywave_button_press_a_trigger_fires_for_group_target(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Purpose-specific trigger fires when configured via a group entity target."""
    await _async_setup_entry(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)}
    )
    assert device is not None
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_TRANSMITTER_DEVICE_ID}_last_button"
    )
    assert entity_id is not None

    assert await async_setup_component(hass, GROUP_DOMAIN, {})
    await group.Group.async_create_group(
        hass,
        "easywave_buttons",
        created_by_service=False,
        entity_ids=[entity_id],
        icon=None,
        mode=None,
        object_id=None,
        order=None,
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "trigger": "easywave.button_press_a",
                    "target": {"entity_id": "group.easywave_buttons"},
                },
                "action": {
                    "service": "test.automation",
                    "data": {"subtype": "{{ trigger.event.data.subtype }}"},
                },
            }
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_EASYWAVE,
        {
            "device_id": device.id,
            "type": EVENT_TYPE_BUTTON_PRESS,
            "subtype": "a",
        },
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["subtype"] == "a"


async def test_easywave_gateway_connected_trigger_fires(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Purpose-specific easywave.gateway_connected trigger fires on matching events."""
    entry = await _async_setup_entry(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "trigger": "easywave.gateway_connected",
                    "target": {"device_id": device.id},
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_EASYWAVE,
        {
            "device_id": device.id,
            "type": EVENT_TYPE_GATEWAY_CONNECTED,
            "subtype": "connected",
        },
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1


async def test_easywave_button_press_a_trigger_ignores_non_matching_events(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Purpose-specific trigger ignores events with wrong type, device, or subtype."""
    await _async_setup_entry(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)}
    )
    assert device is not None

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "trigger": "easywave.button_press_a",
                    "target": {"device_id": device.id},
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_EASYWAVE,
        {
            "device_id": device.id,
            "type": EVENT_TYPE_BUTTON_RELEASE,
            "subtype": "released",
        },
    )
    hass.bus.async_fire(
        EVENT_EASYWAVE,
        {
            "device_id": "other-device",
            "type": EVENT_TYPE_BUTTON_PRESS,
            "subtype": "a",
        },
    )
    hass.bus.async_fire(
        EVENT_EASYWAVE,
        {
            "device_id": device.id,
            "type": EVENT_TYPE_BUTTON_PRESS,
            "subtype": "b",
        },
    )
    await hass.async_block_till_done()

    assert service_calls == []


async def test_get_triggers_for_target_transmitter(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Target-based automation UI lists only configured transmitter button triggers."""
    await _async_setup_entry(hass, button_count=2)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)}
    )
    assert device is not None

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "get_triggers_for_target",
            "target": {"device_id": device.id},
            "expand_group": True,
        }
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert "easywave.button_press_a" in msg["result"]
    assert "easywave.button_press_b" in msg["result"]
    assert "easywave.button_release" in msg["result"]
    assert "easywave.button_press_c" not in msg["result"]
    assert "easywave.button_press_d" not in msg["result"]
    assert "easywave.gateway_connected" not in msg["result"]
    assert "easywave.battery_low" not in msg["result"]


async def test_get_triggers_for_target_gateway(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Gateway devices list connection triggers but not transmitter button triggers."""
    entry = await _async_setup_entry(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "get_triggers_for_target",
            "target": {"device_id": device.id},
            "expand_group": True,
        }
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert "easywave.gateway_connected" in msg["result"]
    assert "easywave.gateway_disconnected" in msg["result"]
    assert "easywave.button_press_a" not in msg["result"]
    assert "easywave.button_release" not in msg["result"]
