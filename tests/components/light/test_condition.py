"""Test light conditions."""

import pytest

from homeassistant.components import automation
from homeassistant.const import (
    ATTR_LABEL_ID,
    CONF_CONDITION,
    CONF_STATE,
    CONF_TARGET,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er, label_registry as lr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

# remove when #151314 is merged
CONF_OPTIONS = "options"


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
async def label_entities(hass: HomeAssistant) -> None:
    """Create multiple entities associated with labels."""
    await async_setup_component(hass, "light", {})

    config_entry = MockConfigEntry(domain="test_labels")
    config_entry.add_to_hass(hass)

    label_reg = lr.async_get(hass)
    label = label_reg.async_create("Test Label")

    entity_reg = er.async_get(hass)

    for i in range(3):
        light_entity = entity_reg.async_get_or_create(
            domain="light",
            platform="test",
            unique_id=f"label_light_{i}",
            suggested_object_id=f"label_light_{i}",
        )
        entity_reg.async_update_entity(light_entity.entity_id, labels={label.label_id})

    # Also create switches to test that they don't impact the conditions
    for i in range(2):
        switch_entity = entity_reg.async_get_or_create(
            domain="switch",
            platform="test",
            unique_id=f"label_switch_{i}",
            suggested_object_id=f"label_switch_{i}",
        )
        entity_reg.async_update_entity(switch_entity.entity_id, labels={label.label_id})

    return [
        "light.label_light_0",
        "light.label_light_1",
        "light.label_light_2",
    ]


async def has_calls_after_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> bool:
    """Check if there are service calls after the trigger event."""
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    has_calls = len(service_calls) == 1
    service_calls.clear()
    return has_calls


@pytest.mark.parametrize("condition_state", [STATE_ON, STATE_OFF])
async def test_light_state_condition_behavior_one(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    label_entities: list[str],
    condition_state: str,
) -> None:
    """Test the light state condition with the 'one' behavior."""
    await async_setup_component(hass, "light", {})

    # Set state for two switches to ensure that they don't impact the condition
    hass.states.async_set("switch.label_switch_1", STATE_OFF)
    hass.states.async_set("switch.label_switch_2", STATE_ON)

    reverse_state = STATE_OFF if condition_state == STATE_ON else STATE_ON
    for entity_id in label_entities:
        hass.states.async_set(entity_id, reverse_state)

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    CONF_CONDITION: "light.state",
                    CONF_TARGET: {
                        ATTR_LABEL_ID: "test_label",
                    },
                    CONF_OPTIONS: {"behavior": "one", CONF_STATE: condition_state},
                },
                "action": {
                    "service": "test.automation",
                },
            }
        },
    )

    # No lights on the condition state
    assert not await has_calls_after_trigger(hass, service_calls)

    # Set one light to the condition state -> condition pass
    hass.states.async_set(label_entities[0], condition_state)
    assert await has_calls_after_trigger(hass, service_calls)

    # Set second light to the condition state -> condition fail
    hass.states.async_set(label_entities[1], condition_state)
    assert not await has_calls_after_trigger(hass, service_calls)

    # Set first light to unavailable -> condition pass again since only the
    # second light is on the condition state
    hass.states.async_set(label_entities[0], STATE_UNAVAILABLE)
    assert await has_calls_after_trigger(hass, service_calls)

    # Set all lights to unavailable -> condition fail
    for entity_id in label_entities:
        hass.states.async_set(entity_id, STATE_UNAVAILABLE)
    assert not await has_calls_after_trigger(hass, service_calls)


@pytest.mark.parametrize("condition_state", [STATE_ON, STATE_OFF])
async def test_light_state_condition_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    label_entities: list[str],
    condition_state: str,
) -> None:
    """Test the light state condition with the 'any' behavior."""
    await async_setup_component(hass, "light", {})

    reverse_state = STATE_OFF if condition_state == STATE_ON else STATE_ON
    for entity_id in label_entities:
        hass.states.async_set(entity_id, reverse_state)

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    CONF_CONDITION: "light.state",
                    CONF_TARGET: {
                        ATTR_LABEL_ID: "test_label",
                    },
                    CONF_OPTIONS: {"behavior": "any", CONF_STATE: condition_state},
                },
                "action": {
                    "service": "test.automation",
                },
            }
        },
    )

    # Set state for two switches to ensure that they don't impact the condition
    hass.states.async_set("switch.label_switch_1", STATE_OFF)
    hass.states.async_set("switch.label_switch_2", STATE_ON)

    # No lights on the condition state
    assert not await has_calls_after_trigger(hass, service_calls)

    # Set one light to the condition state -> condition pass
    hass.states.async_set(label_entities[0], condition_state)
    assert await has_calls_after_trigger(hass, service_calls)

    # Set all lights to the condition state -> condition pass
    for entity_id in label_entities:
        hass.states.async_set(entity_id, condition_state)
    assert await has_calls_after_trigger(hass, service_calls)

    # Set one light to unavailable -> condition pass
    hass.states.async_set(label_entities[0], STATE_UNAVAILABLE)
    assert await has_calls_after_trigger(hass, service_calls)

    # Set all lights to unavailable -> condition fail
    for entity_id in label_entities:
        hass.states.async_set(entity_id, STATE_UNAVAILABLE)
    assert not await has_calls_after_trigger(hass, service_calls)


@pytest.mark.parametrize("condition_state", [STATE_ON, STATE_OFF])
async def test_light_state_condition_behavior_all(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    label_entities: list[str],
    condition_state: str,
) -> None:
    """Test the light state condition with the 'all' behavior."""
    await async_setup_component(hass, "light", {})

    # Set state for two switches to ensure that they don't impact the condition
    hass.states.async_set("switch.label_switch_1", STATE_OFF)
    hass.states.async_set("switch.label_switch_2", STATE_ON)

    reverse_state = STATE_OFF if condition_state == STATE_ON else STATE_ON
    for entity_id in label_entities:
        hass.states.async_set(entity_id, reverse_state)

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    CONF_CONDITION: "light.state",
                    CONF_TARGET: {
                        ATTR_LABEL_ID: "test_label",
                    },
                    CONF_OPTIONS: {"behavior": "all", CONF_STATE: condition_state},
                },
                "action": {
                    "service": "test.automation",
                },
            }
        },
    )

    # No lights on the condition state
    assert not await has_calls_after_trigger(hass, service_calls)

    # Set one light to the condition state -> condition fail
    hass.states.async_set(label_entities[0], condition_state)
    assert not await has_calls_after_trigger(hass, service_calls)

    # Set all lights to the condition state -> condition pass
    for entity_id in label_entities:
        hass.states.async_set(entity_id, condition_state)
    assert await has_calls_after_trigger(hass, service_calls)

    # Set one light to unavailable -> condition should still pass
    hass.states.async_set(label_entities[0], STATE_UNAVAILABLE)

    # Set all lights to unavailable -> condition fail
    for entity_id in label_entities:
        hass.states.async_set(entity_id, STATE_UNAVAILABLE)
    assert not await has_calls_after_trigger(hass, service_calls)
