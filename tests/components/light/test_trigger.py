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


async def test_light_brightness_changed_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the brightness changed trigger fires when brightness changes."""
    entity_id = "light.test_light"
    await async_setup_component(hass, "light", {})

    # Set initial state with brightness
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 100})
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "light.brightness_changed",
                    "target": {CONF_ENTITY_ID: entity_id},
                },
                "actions": {
                    "action": "test.automation",
                    "data": {
                        CONF_ENTITY_ID: "{{ trigger.entity_id }}",
                        "from_brightness": "{{ trigger.from_brightness }}",
                        "to_brightness": "{{ trigger.to_brightness }}",
                    },
                },
            }
        },
    )

    # Change brightness - should trigger
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 150})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    assert service_calls[0].data["from_brightness"] == "100"
    assert service_calls[0].data["to_brightness"] == "150"
    service_calls.clear()

    # Change brightness again - should trigger
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 200})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["from_brightness"] == "150"
    assert service_calls[0].data["to_brightness"] == "200"


async def test_light_brightness_changed_trigger_same_brightness(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the brightness changed trigger does not fire when brightness is the same."""
    entity_id = "light.test_light"
    await async_setup_component(hass, "light", {})

    # Set initial state with brightness
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 100})
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "light.brightness_changed",
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

    # Update state but keep brightness the same - should not trigger
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 100})
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_light_brightness_changed_trigger_with_lower_limit(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the brightness changed trigger with lower limit."""
    entity_id = "light.test_light"
    await async_setup_component(hass, "light", {})

    # Set initial state with brightness
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 50})
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "light.brightness_changed",
                    "target": {CONF_ENTITY_ID: entity_id},
                    "options": {
                        "lower": 100,
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

    # Change to brightness below lower limit - should not trigger
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 75})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Change to brightness at lower limit - should trigger
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 100})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    service_calls.clear()

    # Change to brightness above lower limit - should trigger
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 150})
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_light_brightness_changed_trigger_with_upper_limit(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the brightness changed trigger with upper limit."""
    entity_id = "light.test_light"
    await async_setup_component(hass, "light", {})

    # Set initial state with brightness
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 200})
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "light.brightness_changed",
                    "target": {CONF_ENTITY_ID: entity_id},
                    "options": {
                        "upper": 150,
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

    # Change to brightness above upper limit - should not trigger
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 180})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Change to brightness at upper limit - should trigger
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 150})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    service_calls.clear()

    # Change to brightness below upper limit - should trigger
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 100})
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_light_brightness_changed_trigger_with_above(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the brightness changed trigger with above threshold."""
    entity_id = "light.test_light"
    await async_setup_component(hass, "light", {})

    # Set initial state with brightness
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 50})
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "light.brightness_changed",
                    "target": {CONF_ENTITY_ID: entity_id},
                    "options": {
                        "above": 100,
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

    # Change to brightness at threshold - should not trigger
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 100})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Change to brightness above threshold - should trigger
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 101})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    service_calls.clear()

    # Change to brightness well above threshold - should trigger
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 200})
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_light_brightness_changed_trigger_with_below(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the brightness changed trigger with below threshold."""
    entity_id = "light.test_light"
    await async_setup_component(hass, "light", {})

    # Set initial state with brightness
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 200})
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "light.brightness_changed",
                    "target": {CONF_ENTITY_ID: entity_id},
                    "options": {
                        "below": 100,
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

    # Change to brightness at threshold - should not trigger
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 100})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Change to brightness below threshold - should trigger
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 99})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    service_calls.clear()

    # Change to brightness well below threshold - should trigger
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_light_brightness_changed_trigger_ignores_unavailable(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the brightness changed trigger ignores unavailable states."""
    entity_id = "light.test_light"
    await async_setup_component(hass, "light", {})

    # Set initial state with brightness
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 100})
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "light.brightness_changed",
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

    # Change brightness after unavailable - should trigger
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 150})
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_light_brightness_changed_trigger_from_no_brightness(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the trigger fires when brightness is added."""
    entity_id = "light.test_light"
    await async_setup_component(hass, "light", {})

    # Set initial state without brightness (on/off only light)
    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "light.brightness_changed",
                    "target": {CONF_ENTITY_ID: entity_id},
                },
                "actions": {
                    "action": "test.automation",
                    "data": {
                        CONF_ENTITY_ID: "{{ trigger.entity_id }}",
                        "from_brightness": "{{ trigger.from_brightness }}",
                        "to_brightness": "{{ trigger.to_brightness }}",
                    },
                },
            }
        },
    )

    # Add brightness attribute - should trigger
    hass.states.async_set(entity_id, STATE_ON, {"brightness": 100})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["from_brightness"] == "None"
    assert service_calls[0].data["to_brightness"] == "100"


async def test_light_brightness_changed_trigger_no_brightness(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the trigger does not fire when brightness is not present."""
    entity_id = "light.test_light"
    await async_setup_component(hass, "light", {})

    # Set initial state without brightness
    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "light.brightness_changed",
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

    # Turn light off and on without brightness - should not trigger
    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert len(service_calls) == 0
