"""The tests for Select device actions."""
import pytest
import voluptuous_serialize

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.select import DOMAIN
from homeassistant.components.select.device_action import async_get_action_capabilities
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
)


async def test_get_actions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected actions from a select."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )
    expected_actions = [
        {
            "domain": DOMAIN,
            "type": action,
            "device_id": device_entry.id,
            "entity_id": "select.test_5678",
            "metadata": {"secondary": False},
        }
        for action in [
            "select_first",
            "select_last",
            "select_next",
            "select_option",
            "select_previous",
        ]
    ]
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert_lists_same(actions, expected_actions)


@pytest.mark.parametrize(
    ("hidden_by", "entity_category"),
    (
        (er.RegistryEntryHider.INTEGRATION, None),
        (er.RegistryEntryHider.USER, None),
        (None, EntityCategory.CONFIG),
        (None, EntityCategory.DIAGNOSTIC),
    ),
)
async def test_get_actions_hidden_auxiliary(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hidden_by,
    entity_category,
) -> None:
    """Test we get the expected actions from a hidden or auxiliary entity."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        "5678",
        device_id=device_entry.id,
        entity_category=entity_category,
        hidden_by=hidden_by,
    )
    expected_actions = []
    expected_actions += [
        {
            "domain": DOMAIN,
            "type": action,
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
            "metadata": {"secondary": True},
        }
        for action in [
            "select_first",
            "select_last",
            "select_next",
            "select_option",
            "select_previous",
        ]
    ]
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert_lists_same(actions, expected_actions)


@pytest.mark.parametrize("action_type", ("select_first", "select_last"))
async def test_action_select_first_last(hass: HomeAssistant, action_type: str) -> None:
    """Test for select_first and select_last actions."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "select.entity",
                        "type": action_type,
                    },
                },
            ]
        },
    )

    select_calls = async_mock_service(hass, DOMAIN, action_type)

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(select_calls) == 1
    assert select_calls[0].domain == DOMAIN
    assert select_calls[0].service == action_type
    assert select_calls[0].data == {"entity_id": "select.entity"}


async def test_action_select_option(hass: HomeAssistant) -> None:
    """Test for select_option action."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "select.entity",
                        "type": "select_option",
                        "option": "option1",
                    },
                },
            ]
        },
    )

    select_calls = async_mock_service(hass, DOMAIN, "select_option")

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(select_calls) == 1
    assert select_calls[0].domain == DOMAIN
    assert select_calls[0].service == "select_option"
    assert select_calls[0].data == {"entity_id": "select.entity", "option": "option1"}


@pytest.mark.parametrize("action_type", ["select_next", "select_previous"])
async def test_action_select_next_previous(
    hass: HomeAssistant, action_type: str
) -> None:
    """Test for select_next and select_previous actions."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "select.entity",
                        "type": action_type,
                        "cycle": False,
                    },
                },
            ]
        },
    )

    select_calls = async_mock_service(hass, DOMAIN, action_type)

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(select_calls) == 1
    assert select_calls[0].domain == DOMAIN
    assert select_calls[0].service == action_type
    assert select_calls[0].data == {"entity_id": "select.entity", "cycle": False}


async def test_get_action_capabilities(hass: HomeAssistant) -> None:
    """Test we get the expected capabilities from a select action."""
    config = {
        "platform": "device",
        "domain": DOMAIN,
        "type": "select_option",
        "entity_id": "select.test",
        "option": "option1",
    }

    # Test when entity doesn't exists
    capabilities = await async_get_action_capabilities(hass, config)
    assert capabilities
    assert "extra_fields" in capabilities
    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "option",
            "required": True,
            "type": "select",
            "options": [],
        },
    ]

    # Mock an entity
    hass.states.async_set("select.test", "option1", {"options": ["option1", "option2"]})

    # Test if we get the right capabilities now
    capabilities = await async_get_action_capabilities(hass, config)
    assert capabilities
    assert "extra_fields" in capabilities
    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "option",
            "required": True,
            "type": "select",
            "options": [("option1", "option1"), ("option2", "option2")],
        },
    ]

    # Test next/previous actions
    config = {
        "platform": "device",
        "domain": DOMAIN,
        "type": "select_next",
        "entity_id": "select.test",
    }
    capabilities = await async_get_action_capabilities(hass, config)
    assert capabilities
    assert "extra_fields" in capabilities
    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "cycle",
            "optional": True,
            "type": "boolean",
            "default": True,
        },
    ]

    config["type"] = "select_previous"
    capabilities = await async_get_action_capabilities(hass, config)
    assert capabilities
    assert "extra_fields" in capabilities
    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "cycle",
            "optional": True,
            "type": "boolean",
            "default": True,
        },
    ]

    # Test action types without extra fields
    config = {
        "platform": "device",
        "domain": DOMAIN,
        "type": "select_first",
        "entity_id": "select.test",
    }
    capabilities = await async_get_action_capabilities(hass, config)
    assert capabilities == {}

    config["type"] = "select_last"
    capabilities = await async_get_action_capabilities(hass, config)
    assert capabilities == {}
