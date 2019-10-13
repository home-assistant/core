"""The tests for Alarm control panel device actions."""
import pytest

from homeassistant.components.alarm_control_panel import DOMAIN
from homeassistant.setup import async_setup_component
import homeassistant.components.automation as automation
from homeassistant.helpers import device_registry

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_mock_service,
    mock_device_registry,
    mock_registry,
    async_get_device_automations,
    async_get_device_automation_capabilities,
)


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


async def test_get_actions(hass, device_reg, entity_reg):
    """Test we get the expected actions from a alarm_control_panel."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(DOMAIN, "test", "5678", device_id=device_entry.id)
    expected_actions = [
        {
            "domain": DOMAIN,
            "type": "arm_away",
            "device_id": device_entry.id,
            "entity_id": "alarm_control_panel.test_5678",
        },
        {
            "domain": DOMAIN,
            "type": "arm_home",
            "device_id": device_entry.id,
            "entity_id": "alarm_control_panel.test_5678",
        },
        {
            "domain": DOMAIN,
            "type": "arm_night",
            "device_id": device_entry.id,
            "entity_id": "alarm_control_panel.test_5678",
        },
        {
            "domain": DOMAIN,
            "type": "disarm",
            "device_id": device_entry.id,
            "entity_id": "alarm_control_panel.test_5678",
        },
        {
            "domain": DOMAIN,
            "type": "trigger",
            "device_id": device_entry.id,
            "entity_id": "alarm_control_panel.test_5678",
        },
    ]
    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert_lists_same(actions, expected_actions)


async def test_get_action_capabilities(hass, device_reg, entity_reg):
    """Test we get the expected capabilities from a sensor trigger."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(DOMAIN, "test", "5678", device_id=device_entry.id)

    expected_capabilities = {
        "arm_away": {"extra_fields": []},
        "arm_home": {"extra_fields": []},
        "arm_night": {"extra_fields": []},
        "disarm": {
            "extra_fields": [{"name": "code", "optional": True, "type": "string"}]
        },
        "trigger": {"extra_fields": []},
    }
    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert len(actions) == 5
    for action in actions:
        capabilities = await async_get_device_automation_capabilities(
            hass, "action", action
        )
        assert capabilities == expected_capabilities[action["type"]]


async def test_action(hass):
    """Test for turn_on and turn_off actions."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_arm_away",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "alarm_control_panel.entity",
                        "type": "arm_away",
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_arm_home",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "alarm_control_panel.entity",
                        "type": "arm_home",
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_arm_night",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "alarm_control_panel.entity",
                        "type": "arm_night",
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event_disarm"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "alarm_control_panel.entity",
                        "type": "disarm",
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_trigger",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "alarm_control_panel.entity",
                        "type": "trigger",
                    },
                },
            ]
        },
    )

    arm_away_calls = async_mock_service(hass, "alarm_control_panel", "arm_away")
    arm_home_calls = async_mock_service(hass, "alarm_control_panel", "arm_home")
    arm_night_calls = async_mock_service(hass, "alarm_control_panel", "arm_night")
    disarm_calls = async_mock_service(hass, "alarm_control_panel", "disarm")
    trigger_calls = async_mock_service(hass, "alarm_control_panel", "trigger")

    hass.bus.async_fire("test_event_arm_away")
    await hass.async_block_till_done()
    assert len(arm_away_calls) == 1
    assert len(arm_home_calls) == 0
    assert len(arm_night_calls) == 0
    assert len(disarm_calls) == 0
    assert len(trigger_calls) == 0

    hass.bus.async_fire("test_event_arm_home")
    await hass.async_block_till_done()
    assert len(arm_away_calls) == 1
    assert len(arm_home_calls) == 1
    assert len(arm_night_calls) == 0
    assert len(disarm_calls) == 0
    assert len(trigger_calls) == 0

    hass.bus.async_fire("test_event_arm_night")
    await hass.async_block_till_done()
    assert len(arm_away_calls) == 1
    assert len(arm_home_calls) == 1
    assert len(arm_night_calls) == 1
    assert len(disarm_calls) == 0
    assert len(trigger_calls) == 0

    hass.bus.async_fire("test_event_disarm")
    await hass.async_block_till_done()
    assert len(arm_away_calls) == 1
    assert len(arm_home_calls) == 1
    assert len(arm_night_calls) == 1
    assert len(disarm_calls) == 1
    assert len(trigger_calls) == 0

    hass.bus.async_fire("test_event_trigger")
    await hass.async_block_till_done()
    assert len(arm_away_calls) == 1
    assert len(arm_home_calls) == 1
    assert len(arm_night_calls) == 1
    assert len(disarm_calls) == 1
    assert len(trigger_calls) == 1
