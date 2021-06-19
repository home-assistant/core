"""The tests for Z-Wave JS device conditions."""
from __future__ import annotations

import pytest
from zwave_js_server.event import Event

from homeassistant.components import automation
from homeassistant.components.zwave_js import DOMAIN
from homeassistant.helpers import device_registry
from homeassistant.setup import async_setup_component

from tests.common import async_get_device_automations, async_mock_service


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_conditions(hass, client, lock_schlage_be469, integration) -> None:
    """Test we get the expected conditions from a zwave_js."""
    dev_reg = device_registry.async_get(hass)
    device = device_registry.async_entries_for_config_entry(
        dev_reg, integration.entry_id
    )[0]
    expected_conditions = [
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": "alive",
            "device_id": device.id,
        },
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": "awake",
            "device_id": device.id,
        },
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": "asleep",
            "device_id": device.id,
        },
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": "dead",
            "device_id": device.id,
        },
    ]
    conditions = await async_get_device_automations(hass, "condition", device.id)
    for condition in expected_conditions:
        assert condition in conditions


async def test_if_state(hass, client, lock_schlage_be469, integration, calls) -> None:
    """Test for turn_on and turn_off conditions."""
    dev_reg = device_registry.async_get(hass)
    device = device_registry.async_entries_for_config_entry(
        dev_reg, integration.entry_id
    )[0]

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event1"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device.id,
                            "type": "alive",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "alive - {{ trigger.platform }} - {{ trigger.event.event_type }}"
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event2"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device.id,
                            "type": "awake",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "awake - {{ trigger.platform }} - {{ trigger.event.event_type }}"
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event3"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device.id,
                            "type": "asleep",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "asleep - {{ trigger.platform }} - {{ trigger.event.event_type }}"
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event4"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device.id,
                            "type": "dead",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "dead - {{ trigger.platform }} - {{ trigger.event.event_type }}"
                        },
                    },
                },
            ]
        },
    )

    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    hass.bus.async_fire("test_event3")
    hass.bus.async_fire("test_event4")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "alive - event - test_event1"

    event = Event(
        "wake up",
        data={
            "source": "node",
            "event": "wake up",
            "nodeId": lock_schlage_be469.node_id,
        },
    )
    lock_schlage_be469.receive_event(event)
    await hass.async_block_till_done()

    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    hass.bus.async_fire("test_event3")
    hass.bus.async_fire("test_event4")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "awake - event - test_event2"

    event = Event(
        "sleep",
        data={"source": "node", "event": "sleep", "nodeId": lock_schlage_be469.node_id},
    )
    lock_schlage_be469.receive_event(event)
    await hass.async_block_till_done()

    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    hass.bus.async_fire("test_event3")
    hass.bus.async_fire("test_event4")
    await hass.async_block_till_done()
    assert len(calls) == 3
    assert calls[2].data["some"] == "asleep - event - test_event3"

    event = Event(
        "dead",
        data={"source": "node", "event": "dead", "nodeId": lock_schlage_be469.node_id},
    )
    lock_schlage_be469.receive_event(event)
    await hass.async_block_till_done()

    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    hass.bus.async_fire("test_event3")
    hass.bus.async_fire("test_event4")
    await hass.async_block_till_done()
    assert len(calls) == 4
    assert calls[3].data["some"] == "dead - event - test_event4"

    event = Event(
        "unknown",
        data={
            "source": "node",
            "event": "unknown",
            "nodeId": lock_schlage_be469.node_id,
        },
    )
    lock_schlage_be469.receive_event(event)
    await hass.async_block_till_done()
