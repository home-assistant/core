"""The tests for Number device actions."""
import pytest
import voluptuous_serialize

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.number import DOMAIN, device_action
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.entity_registry import RegistryEntryHider
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
)
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401


async def test_get_actions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected actions for an entity."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )
    hass.states.async_set("number.test_5678", 0.5, {"min_value": 0.0, "max_value": 1.0})
    expected_actions = [
        {
            "domain": DOMAIN,
            "type": "set_value",
            "device_id": device_entry.id,
            "entity_id": "number.test_5678",
            "metadata": {"secondary": False},
        },
    ]
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert_lists_same(actions, expected_actions)


@pytest.mark.parametrize(
    ("hidden_by", "entity_category"),
    (
        (RegistryEntryHider.INTEGRATION, None),
        (RegistryEntryHider.USER, None),
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
        for action in ["set_value"]
    ]
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert_lists_same(actions, expected_actions)


async def test_get_action_no_state(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected actions for an entity."""
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
            "type": "set_value",
            "device_id": device_entry.id,
            "entity_id": "number.test_5678",
            "metadata": {"secondary": False},
        },
    ]
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert_lists_same(actions, expected_actions)


async def test_action(hass: HomeAssistant) -> None:
    """Test for actions."""
    hass.states.async_set("number.entity", 0.5, {"min_value": 0.0, "max_value": 1.0})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_value",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "number.entity",
                        "type": "set_value",
                        "value": 0.3,
                    },
                },
            ]
        },
    )

    calls = async_mock_service(hass, DOMAIN, "set_value")

    assert len(calls) == 0

    hass.bus.async_fire("test_event_set_value")
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_capabilities(hass: HomeAssistant) -> None:
    """Test getting capabilities."""
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "domain": DOMAIN,
            "device_id": "abcdefgh",
            "entity_id": "number.entity",
            "type": "set_value",
        },
    )

    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [{"name": "value", "required": True, "type": "float"}]
