"""Test media_player trigger."""

from homeassistant.components import automation
from homeassistant.const import (
    CONF_ENTITY_ID,
    STATE_IDLE,
    STATE_OFF,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component


async def test_turns_on_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the turns on trigger fires when a media player turns on."""
    entity_id = "media_player.test"
    await async_setup_component(hass, "media_player", {})

    # Set initial state to off
    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "media_player.turns_on",
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

    # Turn on - should trigger
    hass.states.async_set(entity_id, STATE_IDLE)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Already on, change to playing - should not trigger
    hass.states.async_set(entity_id, STATE_PLAYING)
    await hass.async_block_till_done()
    assert len(service_calls) == 0
