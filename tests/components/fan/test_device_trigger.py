"""The tests for Fan device triggers."""
from datetime import timedelta

import pytest

import homeassistant.components.automation as automation
from homeassistant.components.fan import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers import device_registry
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_fire_time_changed,
    async_get_device_automation_capabilities,
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


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_triggers(hass, device_reg, entity_reg):
    """Test we get the expected triggers from a fan."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(DOMAIN, "test", "5678", device_id=device_entry.id)
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "turned_off",
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "turned_on",
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
        },
    ]
    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, expected_triggers)


async def test_get_trigger_capabilities(hass, device_reg, entity_reg):
    """Test we get the expected capabilities from a switch trigger."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(DOMAIN, "test", "5678", device_id=device_entry.id)
    expected_capabilities = {
        "extra_fields": [
            {"name": "for", "optional": True, "type": "positive_time_period_dict"}
        ]
    }
    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    for trigger in triggers:
        capabilities = await async_get_device_automation_capabilities(
            hass, "trigger", trigger
        )
        assert capabilities == expected_capabilities


async def test_if_fires_on_state_change(hass, calls):
    """Test for turn_on and turn_off triggers firing."""
    hass.states.async_set("fan.entity", STATE_OFF)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "fan.entity",
                        "type": "turned_on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "turn_on - {{ trigger.platform}} - "
                                "{{ trigger.entity_id}} - {{ trigger.from_state.state}} - "
                                "{{ trigger.to_state.state}} - {{ trigger.for }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "fan.entity",
                        "type": "turned_off",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "turn_off - {{ trigger.platform}} - "
                                "{{ trigger.entity_id}} - {{ trigger.from_state.state}} - "
                                "{{ trigger.to_state.state}} - {{ trigger.for }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    # Fake that the entity is turning on.
    hass.states.async_set("fan.entity", STATE_ON)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "turn_on - device - fan.entity - off - on - None"

    # Fake that the entity is turning off.
    hass.states.async_set("fan.entity", STATE_OFF)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "turn_off - device - fan.entity - on - off - None"


async def test_if_fires_on_state_change_with_for(hass, calls):
    """Test for triggers firing with delay."""
    entity_id = "fan.entity"
    hass.states.async_set(entity_id, STATE_ON)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": entity_id,
                        "type": "turned_off",
                        "for": {"seconds": 5},
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "turn_off {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(
                                (
                                    "platform",
                                    "entity_id",
                                    "from_state.state",
                                    "to_state.state",
                                    "for",
                                )
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON
    assert len(calls) == 0

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1
    await hass.async_block_till_done()
    assert (
        calls[0].data["some"] == f"turn_off device - {entity_id} - on - off - 0:00:05"
    )
