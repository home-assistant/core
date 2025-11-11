"""Test light trigger."""

from homeassistant.components import automation
from homeassistant.const import CONF_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component


async def test_light_turns_on_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the light turns on trigger fires when a light turns on."""
    entity_id = "light.test_light"
    await async_setup_component(hass, "light", {})

    # Set initial state to off
    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "light.turns_on",
                    "target": {CONF_ENTITY_ID: entity_id},
                },
                "actions": {
                    "action": "test.automation",
                    "data": {
                        CONF_ENTITY_ID: "{{ trigger.entity_id }}",
                    },
                },
            }
        },
    )

    # Turn light on - should trigger
    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Turn light on again while already on - should not trigger
    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_light_turns_on_trigger_ignores_unavailable(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the light turns on trigger ignores unavailable states."""
    entity_id = "light.test_light"
    await async_setup_component(hass, "light", {})

    # Set initial state to off
    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "light.turns_on",
                    "target": {CONF_ENTITY_ID: entity_id},
                },
                "actions": {
                    "action": "test.automation",
                    "data": {
                        CONF_ENTITY_ID: "{{ trigger.entity_id }}",
                    },
                },
            }
        },
    )

    # Set to unavailable - should not trigger
    hass.states.async_set(entity_id, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Turn light on after unavailable - should not trigger (from unavailable)
    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Turn light off
    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Turn light on after being off - should trigger
    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id


async def test_light_turns_on_multiple_lights(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the turns on trigger with multiple lights."""
    entity_id_1 = "light.test_light_1"
    entity_id_2 = "light.test_light_2"
    await async_setup_component(hass, "light", {})

    # Set initial states to off
    hass.states.async_set(entity_id_1, STATE_OFF)
    hass.states.async_set(entity_id_2, STATE_OFF)
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "light.turns_on",
                    "target": {
                        CONF_ENTITY_ID: [entity_id_1, entity_id_2],
                    },
                },
                "actions": {
                    "action": "test.automation",
                    "data": {
                        CONF_ENTITY_ID: "{{ trigger.entity_id }}",
                    },
                },
            }
        },
    )

    # Turn first light on - should trigger
    hass.states.async_set(entity_id_1, STATE_ON)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id_1
    service_calls.clear()

    # Turn second light on - should trigger
    hass.states.async_set(entity_id_2, STATE_ON)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id_2


async def test_light_turns_off_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the light turns off trigger fires when a light turns off."""
    entity_id = "light.test_light"
    await async_setup_component(hass, "light", {})

    # Set initial state to on
    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "light.turns_off",
                    "target": {CONF_ENTITY_ID: entity_id},
                },
                "actions": {
                    "action": "test.automation",
                    "data": {
                        CONF_ENTITY_ID: "{{ trigger.entity_id }}",
                    },
                },
            }
        },
    )

    # Turn light off - should trigger
    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Turn light off again while already off - should not trigger
    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_light_turns_off_trigger_ignores_unavailable(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the light turns off trigger ignores unavailable states."""
    entity_id = "light.test_light"
    await async_setup_component(hass, "light", {})

    # Set initial state to on
    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "light.turns_off",
                    "target": {CONF_ENTITY_ID: entity_id},
                },
                "actions": {
                    "action": "test.automation",
                    "data": {
                        CONF_ENTITY_ID: "{{ trigger.entity_id }}",
                    },
                },
            }
        },
    )

    # Set to unavailable - should not trigger
    hass.states.async_set(entity_id, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Turn light off after unavailable - should not trigger (from unavailable)
    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Turn light on
    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Turn light off after being on - should trigger
    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
