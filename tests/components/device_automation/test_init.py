"""The test for light device automation."""
import pytest

import homeassistant.components.automation as automation
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.const import CONF_PLATFORM, STATE_OFF, STATE_ON
from homeassistant.helpers import device_registry
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    async_mock_service,
    mock_device_registry,
    mock_registry,
)
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


def _same_lists(a, b):
    if len(a) != len(b):
        return False

    for d in a:
        if d not in b:
            return False
    return True


async def test_websocket_get_actions(hass, hass_ws_client, device_reg, entity_reg):
    """Test we get the expected conditions from a light through websocket."""
    await async_setup_component(hass, "device_automation", {})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create("light", "test", "5678", device_id=device_entry.id)
    expected_actions = [
        {
            "domain": "light",
            "type": "turn_off",
            "device_id": device_entry.id,
            "entity_id": "light.test_5678",
        },
        {
            "domain": "light",
            "type": "turn_on",
            "device_id": device_entry.id,
            "entity_id": "light.test_5678",
        },
        {
            "domain": "light",
            "type": "toggle",
            "device_id": device_entry.id,
            "entity_id": "light.test_5678",
        },
    ]

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "device_automation/action/list", "device_id": device_entry.id}
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    actions = msg["result"]
    assert _same_lists(actions, expected_actions)


async def test_websocket_get_conditions(hass, hass_ws_client, device_reg, entity_reg):
    """Test we get the expected conditions from a light through websocket."""
    await async_setup_component(hass, "device_automation", {})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create("light", "test", "5678", device_id=device_entry.id)
    expected_conditions = [
        {
            "condition": "device",
            "domain": "light",
            "type": "is_off",
            "device_id": device_entry.id,
            "entity_id": "light.test_5678",
        },
        {
            "condition": "device",
            "domain": "light",
            "type": "is_on",
            "device_id": device_entry.id,
            "entity_id": "light.test_5678",
        },
    ]

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/condition/list",
            "device_id": device_entry.id,
        }
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    conditions = msg["result"]
    assert _same_lists(conditions, expected_conditions)


async def test_websocket_get_triggers(hass, hass_ws_client, device_reg, entity_reg):
    """Test we get the expected triggers from a light through websocket."""
    await async_setup_component(hass, "device_automation", {})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create("light", "test", "5678", device_id=device_entry.id)
    expected_triggers = [
        {
            "platform": "device",
            "domain": "light",
            "type": "turned_off",
            "device_id": device_entry.id,
            "entity_id": "light.test_5678",
        },
        {
            "platform": "device",
            "domain": "light",
            "type": "turned_on",
            "device_id": device_entry.id,
            "entity_id": "light.test_5678",
        },
    ]

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/trigger/list",
            "device_id": device_entry.id,
        }
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    triggers = msg["result"]
    assert _same_lists(triggers, expected_triggers)


async def test_websocket_get_action_capabilities(
    hass, hass_ws_client, device_reg, entity_reg
):
    """Test we get the expected action capabilities for an alarm through websocket."""
    await async_setup_component(hass, "device_automation", {})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        "alarm_control_panel", "test", "5678", device_id=device_entry.id
    )
    hass.states.async_set(
        "alarm_control_panel.test_5678", "attributes", {"supported_features": 15}
    )
    expected_capabilities = {
        "arm_away": {"extra_fields": []},
        "arm_home": {"extra_fields": []},
        "arm_night": {"extra_fields": []},
        "disarm": {
            "extra_fields": [{"name": "code", "optional": True, "type": "string"}]
        },
        "trigger": {"extra_fields": []},
    }

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "device_automation/action/list", "device_id": device_entry.id}
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    actions = msg["result"]

    id = 2
    assert len(actions) == 5
    for action in actions:
        await client.send_json(
            {
                "id": id,
                "type": "device_automation/action/capabilities",
                "action": action,
            }
        )
        msg = await client.receive_json()
        assert msg["id"] == id
        assert msg["type"] == TYPE_RESULT
        assert msg["success"]
        capabilities = msg["result"]
        assert capabilities == expected_capabilities[action["type"]]
        id = id + 1


async def test_websocket_get_bad_action_capabilities(
    hass, hass_ws_client, device_reg, entity_reg
):
    """Test we get no action capabilities for a non existing domain."""
    await async_setup_component(hass, "device_automation", {})
    expected_capabilities = {}

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/action/capabilities",
            "action": {"domain": "beer"},
        }
    )
    msg = await client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    capabilities = msg["result"]
    assert capabilities == expected_capabilities


async def test_websocket_get_no_action_capabilities(
    hass, hass_ws_client, device_reg, entity_reg
):
    """Test we get no action capabilities for a domain with no device action capabilities."""
    await async_setup_component(hass, "device_automation", {})
    expected_capabilities = {}

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/action/capabilities",
            "action": {"domain": "deconz"},
        }
    )
    msg = await client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    capabilities = msg["result"]
    assert capabilities == expected_capabilities


async def test_websocket_get_condition_capabilities(
    hass, hass_ws_client, device_reg, entity_reg
):
    """Test we get the expected condition capabilities for a light through websocket."""
    await async_setup_component(hass, "device_automation", {})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create("light", "test", "5678", device_id=device_entry.id)
    expected_capabilities = {
        "extra_fields": [
            {"name": "for", "optional": True, "type": "positive_time_period_dict"}
        ]
    }

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/condition/list",
            "device_id": device_entry.id,
        }
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    conditions = msg["result"]

    id = 2
    assert len(conditions) == 2
    for condition in conditions:
        await client.send_json(
            {
                "id": id,
                "type": "device_automation/condition/capabilities",
                "condition": condition,
            }
        )
        msg = await client.receive_json()
        assert msg["id"] == id
        assert msg["type"] == TYPE_RESULT
        assert msg["success"]
        capabilities = msg["result"]
        assert capabilities == expected_capabilities
        id = id + 1


async def test_websocket_get_bad_condition_capabilities(
    hass, hass_ws_client, device_reg, entity_reg
):
    """Test we get no condition capabilities for a non existing domain."""
    await async_setup_component(hass, "device_automation", {})
    expected_capabilities = {}

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/condition/capabilities",
            "condition": {"domain": "beer"},
        }
    )
    msg = await client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    capabilities = msg["result"]
    assert capabilities == expected_capabilities


async def test_websocket_get_no_condition_capabilities(
    hass, hass_ws_client, device_reg, entity_reg
):
    """Test we get no condition capabilities for a domain with no device condition capabilities."""
    await async_setup_component(hass, "device_automation", {})
    expected_capabilities = {}

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/condition/capabilities",
            "condition": {"domain": "deconz"},
        }
    )
    msg = await client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    capabilities = msg["result"]
    assert capabilities == expected_capabilities


async def test_websocket_get_trigger_capabilities(
    hass, hass_ws_client, device_reg, entity_reg
):
    """Test we get the expected trigger capabilities for a light through websocket."""
    await async_setup_component(hass, "device_automation", {})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create("light", "test", "5678", device_id=device_entry.id)
    expected_capabilities = {
        "extra_fields": [
            {"name": "for", "optional": True, "type": "positive_time_period_dict"}
        ]
    }

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/trigger/list",
            "device_id": device_entry.id,
        }
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    triggers = msg["result"]

    id = 2
    assert len(triggers) == 2
    for trigger in triggers:
        await client.send_json(
            {
                "id": id,
                "type": "device_automation/trigger/capabilities",
                "trigger": trigger,
            }
        )
        msg = await client.receive_json()
        assert msg["id"] == id
        assert msg["type"] == TYPE_RESULT
        assert msg["success"]
        capabilities = msg["result"]
        assert capabilities == expected_capabilities
        id = id + 1


async def test_websocket_get_bad_trigger_capabilities(
    hass, hass_ws_client, device_reg, entity_reg
):
    """Test we get no trigger capabilities for a non existing domain."""
    await async_setup_component(hass, "device_automation", {})
    expected_capabilities = {}

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/trigger/capabilities",
            "trigger": {"domain": "beer"},
        }
    )
    msg = await client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    capabilities = msg["result"]
    assert capabilities == expected_capabilities


async def test_websocket_get_no_trigger_capabilities(
    hass, hass_ws_client, device_reg, entity_reg
):
    """Test we get no trigger capabilities for a domain with no device trigger capabilities."""
    await async_setup_component(hass, "device_automation", {})
    expected_capabilities = {}

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/trigger/capabilities",
            "trigger": {"domain": "deconz"},
        }
    )
    msg = await client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    capabilities = msg["result"]
    assert capabilities == expected_capabilities


async def test_automation_with_non_existing_integration(hass, caplog):
    """Test device automation with non existing integration."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {
                    "platform": "device",
                    "device_id": "none",
                    "domain": "beer",
                },
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    assert "Integration 'beer' not found" in caplog.text


async def test_automation_with_integration_without_device_action(hass, caplog):
    """Test automation with integration without device action support."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event1"},
                "action": {"device_id": "", "domain": "test"},
            }
        },
    )

    assert (
        "Integration 'test' does not support device automation actions" in caplog.text
    )


async def test_automation_with_integration_without_device_condition(hass, caplog):
    """Test automation with integration without device condition support."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event1"},
                "condition": {
                    "condition": "device",
                    "device_id": "none",
                    "domain": "test",
                },
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    assert (
        "Integration 'test' does not support device automation conditions"
        in caplog.text
    )


async def test_automation_with_integration_without_device_trigger(hass, caplog):
    """Test automation with integration without device trigger support."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {
                    "platform": "device",
                    "device_id": "none",
                    "domain": "test",
                },
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    assert (
        "Integration 'test' does not support device automation triggers" in caplog.text
    )


async def test_automation_with_bad_action(hass, caplog):
    """Test automation with bad device action."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event1"},
                "action": {"device_id": "", "domain": "light"},
            }
        },
    )

    assert "required key not provided" in caplog.text


async def test_automation_with_bad_condition_action(hass, caplog):
    """Test automation with bad device action."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event1"},
                "action": {"condition": "device", "device_id": "", "domain": "light"},
            }
        },
    )

    assert "required key not provided" in caplog.text


async def test_automation_with_bad_condition(hass, caplog):
    """Test automation with bad device condition."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event1"},
                "condition": {"condition": "device", "domain": "light"},
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    assert "required key not provided" in caplog.text


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_automation_with_sub_condition(hass, calls):
    """Test automation with device condition under and/or conditions."""
    DOMAIN = "light"
    platform = getattr(hass.components, f"test.{DOMAIN}")

    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()
    ent1, ent2, ent3 = platform.ENTITIES

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event1"},
                    "condition": [
                        {
                            "condition": "and",
                            "conditions": [
                                {
                                    "condition": "device",
                                    "domain": DOMAIN,
                                    "device_id": "",
                                    "entity_id": ent1.entity_id,
                                    "type": "is_on",
                                },
                                {
                                    "condition": "device",
                                    "domain": DOMAIN,
                                    "device_id": "",
                                    "entity_id": ent2.entity_id,
                                    "type": "is_on",
                                },
                            ],
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "and {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(("platform", "event.event_type"))
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event1"},
                    "condition": [
                        {
                            "condition": "or",
                            "conditions": [
                                {
                                    "condition": "device",
                                    "domain": DOMAIN,
                                    "device_id": "",
                                    "entity_id": ent1.entity_id,
                                    "type": "is_on",
                                },
                                {
                                    "condition": "device",
                                    "domain": DOMAIN,
                                    "device_id": "",
                                    "entity_id": ent2.entity_id,
                                    "type": "is_on",
                                },
                            ],
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "or {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(("platform", "event.event_type"))
                        },
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_ON
    assert hass.states.get(ent2.entity_id).state == STATE_OFF
    assert len(calls) == 0

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "or event - test_event1"

    hass.states.async_set(ent1.entity_id, STATE_OFF)
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.states.async_set(ent2.entity_id, STATE_ON)
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "or event - test_event1"

    hass.states.async_set(ent1.entity_id, STATE_ON)
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 4
    assert _same_lists(
        [calls[2].data["some"], calls[3].data["some"]],
        ["or event - test_event1", "and event - test_event1"],
    )


async def test_automation_with_bad_sub_condition(hass, caplog):
    """Test automation with bad device condition under and/or conditions."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event1"},
                "condition": {
                    "condition": "and",
                    "conditions": [{"condition": "device", "domain": "light"}],
                },
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    assert "required key not provided" in caplog.text


async def test_automation_with_bad_trigger(hass, caplog):
    """Test automation with bad device trigger."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "device", "domain": "light"},
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    assert "required key not provided" in caplog.text


async def test_websocket_device_not_found(hass, hass_ws_client):
    """Test calling command with unknown device."""
    await async_setup_component(hass, "device_automation", {})
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "device_automation/action/list", "device_id": "non-existing"}
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert not msg["success"]
    assert msg["error"] == {"code": "not_found", "message": "Device not found"}
