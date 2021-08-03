"""The tests for Select device conditions."""
from __future__ import annotations

import pytest
import voluptuous_serialize

from homeassistant.components import automation
from homeassistant.components.select import DOMAIN
from homeassistant.components.select.device_condition import (
    async_get_condition_capabilities,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    CONF_PLATFORM,
    SERVICE_SELECT_OPTION,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import (
    config_validation as cv,
    device_registry,
    entity_registry,
)
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
    mock_registry,
)
from tests.testing_config.custom_components.test.select import (
    UNIQUE_SELECT_1,
    UNIQUE_SELECT_2,
)


@pytest.fixture
def device_reg(hass: HomeAssistant) -> device_registry.DeviceRegistry:
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass: HomeAssistant) -> entity_registry.EntityRegistry:
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.fixture
def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_conditions(
    hass: HomeAssistant,
    device_reg: device_registry.DeviceRegistry,
    entity_reg: entity_registry.EntityRegistry,
) -> None:
    """Test we get the expected conditions from a select."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(DOMAIN, "test", "5678", device_id=device_entry.id)
    expected_conditions = [
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": "selected_option",
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
        }
    ]
    conditions = await async_get_device_automations(hass, "condition", device_entry.id)
    assert_lists_same(conditions, expected_conditions)


async def test_if_selected_option(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test for selected_option conditions."""
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
                            "entity_id": "select.entity",
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
                            "entity_id": "select.entity",
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
        "select.entity", "option1", {"options": ["option1", "option2"]}
    )
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["result"] == "option1 - event - test_event1"

    hass.states.async_set(
        "select.entity", "option2", {"options": ["option1", "option2"]}
    )
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["result"] == "option2 - event - test_event2"


async def test_get_condition_capabilities(hass: HomeAssistant) -> None:
    """Test we get the expected capabilities from a select condition."""
    config = {
        "platform": "device",
        "domain": DOMAIN,
        "type": "selected_option",
        "entity_id": "select.test",
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
    hass.states.async_set("select.test", "option1", {"options": ["option1", "option2"]})

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


async def test_custom_integration_and_validation(
    hass, device_reg, entity_reg, enable_custom_integrations
):
    """Test we can only select valid options."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    reg_entry_1 = entity_reg.async_get_or_create(
        DOMAIN,
        "test",
        UNIQUE_SELECT_1,
        device_id=device_entry.id,
    )
    reg_entry_2 = entity_reg.async_get_or_create(
        DOMAIN,
        "test",
        UNIQUE_SELECT_2,
        device_id=device_entry.id,
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    assert hass.states.get(reg_entry_1.entity_id).state == "option 1"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_OPTION: "option 2", ATTR_ENTITY_ID: reg_entry_1.entity_id},
        blocking=True,
    )

    hass.states.async_set(reg_entry_1.entity_id, "option 2")
    await hass.async_block_till_done()
    assert hass.states.get(reg_entry_1.entity_id).state == "option 2"

    # test ValueError trigger
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_OPTION: "option invalid", ATTR_ENTITY_ID: reg_entry_1.entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert hass.states.get(reg_entry_1.entity_id).state == "option 2"

    assert hass.states.get(reg_entry_2.entity_id).state == STATE_UNKNOWN

    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_OPTION: "option invalid", ATTR_ENTITY_ID: reg_entry_2.entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert hass.states.get(reg_entry_2.entity_id).state == STATE_UNKNOWN

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_OPTION: "option 3", ATTR_ENTITY_ID: reg_entry_2.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(reg_entry_2.entity_id).state == "option 3"
