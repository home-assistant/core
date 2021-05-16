"""The tests for Humidifier device actions."""
import pytest
import voluptuous_serialize

import homeassistant.components.automation as automation
from homeassistant.components.humidifier import DOMAIN, const, device_action
from homeassistant.const import STATE_ON
from homeassistant.helpers import config_validation as cv, device_registry
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
    mock_registry,
)
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


async def test_get_actions(hass, device_reg, entity_reg):
    """Test we get the expected actions from a humidifier."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(DOMAIN, "test", "5678", device_id=device_entry.id)
    hass.states.async_set("humidifier.test_5678", STATE_ON, {})
    hass.states.async_set(
        "humidifier.test_5678", "attributes", {"supported_features": 1}
    )
    expected_actions = [
        {
            "domain": DOMAIN,
            "type": "turn_on",
            "device_id": device_entry.id,
            "entity_id": "humidifier.test_5678",
        },
        {
            "domain": DOMAIN,
            "type": "turn_off",
            "device_id": device_entry.id,
            "entity_id": "humidifier.test_5678",
        },
        {
            "domain": DOMAIN,
            "type": "toggle",
            "device_id": device_entry.id,
            "entity_id": "humidifier.test_5678",
        },
        {
            "domain": DOMAIN,
            "type": "set_humidity",
            "device_id": device_entry.id,
            "entity_id": "humidifier.test_5678",
        },
        {
            "domain": DOMAIN,
            "type": "set_mode",
            "device_id": device_entry.id,
            "entity_id": "humidifier.test_5678",
        },
    ]
    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert_lists_same(actions, expected_actions)


async def test_get_action_no_modes(hass, device_reg, entity_reg):
    """Test we get the expected actions from a humidifier."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(DOMAIN, "test", "5678", device_id=device_entry.id)
    hass.states.async_set("humidifier.test_5678", STATE_ON, {})
    hass.states.async_set(
        "humidifier.test_5678", "attributes", {"supported_features": 0}
    )
    expected_actions = [
        {
            "domain": DOMAIN,
            "type": "turn_on",
            "device_id": device_entry.id,
            "entity_id": "humidifier.test_5678",
        },
        {
            "domain": DOMAIN,
            "type": "turn_off",
            "device_id": device_entry.id,
            "entity_id": "humidifier.test_5678",
        },
        {
            "domain": DOMAIN,
            "type": "toggle",
            "device_id": device_entry.id,
            "entity_id": "humidifier.test_5678",
        },
        {
            "domain": DOMAIN,
            "type": "set_humidity",
            "device_id": device_entry.id,
            "entity_id": "humidifier.test_5678",
        },
    ]
    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert_lists_same(actions, expected_actions)


async def test_get_action_no_state(hass, device_reg, entity_reg):
    """Test we get the expected actions from a humidifier."""
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
            "type": "turn_on",
            "device_id": device_entry.id,
            "entity_id": "humidifier.test_5678",
        },
        {
            "domain": DOMAIN,
            "type": "turn_off",
            "device_id": device_entry.id,
            "entity_id": "humidifier.test_5678",
        },
        {
            "domain": DOMAIN,
            "type": "toggle",
            "device_id": device_entry.id,
            "entity_id": "humidifier.test_5678",
        },
        {
            "domain": DOMAIN,
            "type": "set_humidity",
            "device_id": device_entry.id,
            "entity_id": "humidifier.test_5678",
        },
    ]
    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert_lists_same(actions, expected_actions)


async def test_action(hass):
    """Test for actions."""
    hass.states.async_set(
        "humidifier.entity",
        STATE_ON,
        {const.ATTR_AVAILABLE_MODES: [const.MODE_HOME, const.MODE_AWAY]},
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_turn_off",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "humidifier.entity",
                        "type": "turn_off",
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_turn_on",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "humidifier.entity",
                        "type": "turn_on",
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event_toggle"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "humidifier.entity",
                        "type": "toggle",
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_humidity",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "humidifier.entity",
                        "type": "set_humidity",
                        "humidity": 35,
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_mode",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "humidifier.entity",
                        "type": "set_mode",
                        "mode": const.MODE_AWAY,
                    },
                },
            ]
        },
    )

    set_humidity_calls = async_mock_service(hass, "humidifier", "set_humidity")
    set_mode_calls = async_mock_service(hass, "humidifier", "set_mode")
    turn_on_calls = async_mock_service(hass, "humidifier", "turn_on")
    turn_off_calls = async_mock_service(hass, "humidifier", "turn_off")
    toggle_calls = async_mock_service(hass, "humidifier", "toggle")

    assert len(set_humidity_calls) == 0
    assert len(set_mode_calls) == 0
    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(toggle_calls) == 0

    hass.bus.async_fire("test_event_set_humidity")
    await hass.async_block_till_done()
    assert len(set_humidity_calls) == 1
    assert len(set_mode_calls) == 0
    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(toggle_calls) == 0

    hass.bus.async_fire("test_event_set_mode")
    await hass.async_block_till_done()
    assert len(set_humidity_calls) == 1
    assert len(set_mode_calls) == 1
    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(toggle_calls) == 0

    hass.bus.async_fire("test_event_turn_off")
    await hass.async_block_till_done()
    assert len(set_humidity_calls) == 1
    assert len(set_mode_calls) == 1
    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 1
    assert len(toggle_calls) == 0

    hass.bus.async_fire("test_event_turn_on")
    await hass.async_block_till_done()
    assert len(set_humidity_calls) == 1
    assert len(set_mode_calls) == 1
    assert len(turn_on_calls) == 1
    assert len(turn_off_calls) == 1
    assert len(toggle_calls) == 0

    hass.bus.async_fire("test_event_toggle")
    await hass.async_block_till_done()
    assert len(set_humidity_calls) == 1
    assert len(set_mode_calls) == 1
    assert len(turn_on_calls) == 1
    assert len(turn_off_calls) == 1
    assert len(toggle_calls) == 1


async def test_capabilities(hass):
    """Test getting capabilities."""
    # Test capabililities without state
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "domain": DOMAIN,
            "device_id": "abcdefgh",
            "entity_id": "humidifier.entity",
            "type": "set_mode",
        },
    )

    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [{"name": "mode", "options": [], "required": True, "type": "select"}]

    # Set state
    hass.states.async_set(
        "humidifier.entity",
        STATE_ON,
        {const.ATTR_AVAILABLE_MODES: [const.MODE_HOME, const.MODE_AWAY]},
    )

    # Set humidity
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "domain": DOMAIN,
            "device_id": "abcdefgh",
            "entity_id": "humidifier.entity",
            "type": "set_humidity",
        },
    )

    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [{"name": "humidity", "required": True, "type": "integer"}]

    # Set mode
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "domain": DOMAIN,
            "device_id": "abcdefgh",
            "entity_id": "humidifier.entity",
            "type": "set_mode",
        },
    )

    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "mode",
            "options": [("home", "home"), ("away", "away")],
            "required": True,
            "type": "select",
        }
    ]
