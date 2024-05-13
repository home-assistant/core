"""The tests for Select device conditions."""
from __future__ import annotations

import pytest
from pytest_unordered import unordered
import voluptuous_serialize

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.select import DOMAIN
from homeassistant.components.select.device_condition import (
    async_get_condition_capabilities,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    async_get_device_automations,
    async_mock_service,
)


@pytest.fixture
def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_conditions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected conditions from a select."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )
    expected_conditions = [
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": "selected_option",
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        }
    ]
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert conditions == unordered(expected_conditions)


@pytest.mark.parametrize(
    ("hidden_by", "entity_category"),
    (
        (er.RegistryEntryHider.INTEGRATION, None),
        (er.RegistryEntryHider.USER, None),
        (None, EntityCategory.CONFIG),
        (None, EntityCategory.DIAGNOSTIC),
    ),
)
async def test_get_conditions_hidden_auxiliary(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hidden_by,
    entity_category,
) -> None:
    """Test we get the expected conditions from a hidden or auxiliary entity."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        "5678",
        device_id=device_entry.id,
        entity_category=entity_category,
        hidden_by=hidden_by,
    )
    expected_conditions = [
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": condition,
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": True},
        }
        for condition in ["selected_option"]
    ]
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert conditions == unordered(expected_conditions)


async def test_if_selected_option(
    hass: HomeAssistant,
    calls: list[ServiceCall],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for selected_option conditions."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

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
                            "device_id": "",
                            "entity_id": entry.id,
                            "type": "selected_option",
                            "option": "option1",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data": {
                            "result": "option1 - {{ trigger.platform }} - {{ trigger.event.event_type }}"
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event2"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": "",
                            "entity_id": entry.id,
                            "type": "selected_option",
                            "option": "option2",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data": {
                            "result": "option2 - {{ trigger.platform }} - {{ trigger.event.event_type }}"
                        },
                    },
                },
            ]
        },
    )

    # Test with non existing entity
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.states.async_set(
        entry.entity_id, "option1", {"options": ["option1", "option2"]}
    )
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["result"] == "option1 - event - test_event1"

    hass.states.async_set(
        entry.entity_id, "option2", {"options": ["option1", "option2"]}
    )
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["result"] == "option2 - event - test_event2"


async def test_if_selected_option_legacy(
    hass: HomeAssistant,
    calls: list[ServiceCall],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for selected_option conditions."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

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
                            "device_id": "",
                            "entity_id": entry.entity_id,
                            "type": "selected_option",
                            "option": "option1",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data": {
                            "result": "option1 - {{ trigger.platform }} - {{ trigger.event.event_type }}"
                        },
                    },
                },
            ]
        },
    )

    hass.states.async_set(
        entry.entity_id, "option1", {"options": ["option1", "option2"]}
    )
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["result"] == "option1 - event - test_event1"


async def test_get_condition_capabilities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test we get the expected capabilities from a select condition."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

    config = {
        "platform": "device",
        "domain": DOMAIN,
        "type": "selected_option",
        "entity_id": entry.id,
        "option": "option1",
    }

    # Test when entity doesn't exists
    capabilities = await async_get_condition_capabilities(hass, config)
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
        {
            "name": "for",
            "optional": True,
            "type": "positive_time_period_dict",
        },
    ]

    # Mock an entity
    hass.states.async_set(
        entry.entity_id, "option1", {"options": ["option1", "option2"]}
    )

    # Test if we get the right capabilities now
    capabilities = await async_get_condition_capabilities(hass, config)
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
        {
            "name": "for",
            "optional": True,
            "type": "positive_time_period_dict",
        },
    ]


async def test_get_condition_capabilities_legacy(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test we get the expected capabilities from a select condition."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

    config = {
        "platform": "device",
        "domain": DOMAIN,
        "type": "selected_option",
        "entity_id": entry.entity_id,
        "option": "option1",
    }

    # Test when entity doesn't exists
    capabilities = await async_get_condition_capabilities(hass, config)
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
        {
            "name": "for",
            "optional": True,
            "type": "positive_time_period_dict",
        },
    ]

    # Mock an entity
    hass.states.async_set(
        entry.entity_id, "option1", {"options": ["option1", "option2"]}
    )

    # Test if we get the right capabilities now
    capabilities = await async_get_condition_capabilities(hass, config)
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
        {
            "name": "for",
            "optional": True,
            "type": "positive_time_period_dict",
        },
    ]
