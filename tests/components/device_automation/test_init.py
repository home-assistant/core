"""The test for light device automation."""
import pytest

from homeassistant.setup import async_setup_component
import homeassistant.components.automation as automation
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.helpers import device_registry


from tests.common import MockConfigEntry, mock_device_registry, mock_registry


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
