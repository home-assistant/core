"""The tests for Select device actions."""
import pytest
import voluptuous_serialize

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.select import DOMAIN
from homeassistant.components.select.device_action import async_get_action_capabilities
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry,
    entity_registry,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
    mock_registry,
)


@pytest.fixture
def device_reg(hass: HomeAssistant) -> device_registry.DeviceRegistry:
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass: HomeAssistant) -> entity_registry.EntityRegistry:
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


async def test_get_actions(
    hass: HomeAssistant,
    device_reg: device_registry.DeviceRegistry,
    entity_reg: entity_registry.EntityRegistry,
) -> None:
    """Test we get the expected actions from a select."""
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
            "type": "select_option",
            "device_id": device_entry.id,
            "entity_id": "select.test_5678",
            "metadata": {"secondary": False},
        }
    ]
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert_lists_same(actions, expected_actions)


@pytest.mark.parametrize(
    "hidden_by,entity_category",
    (
        (entity_registry.RegistryEntryHider.INTEGRATION, None),
        (entity_registry.RegistryEntryHider.USER, None),
        (None, EntityCategory.CONFIG),
        (None, EntityCategory.DIAGNOSTIC),
    ),
)
async def test_get_actions_hidden_auxiliary(
    hass,
    device_reg,
    entity_reg,
    hidden_by,
    entity_category,
):
    """Test we get the expected actions from a hidden or auxiliary entity."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
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
        for action in ["select_option"]
    ]
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert_lists_same(actions, expected_actions)


async def test_action(hass: HomeAssistant) -> None:
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
