"""Test media_player trigger."""

from homeassistant.components import automation
from homeassistant.components.media_player import ATTR_MEDIA_CONTENT_TYPE
from homeassistant.const import (
    CONF_ENTITY_ID,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
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


async def test_turns_off_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the turns off trigger fires when a media player turns off."""
    entity_id = "media_player.test"
    await async_setup_component(hass, "media_player", {})

    # Set initial state to playing
    hass.states.async_set(entity_id, STATE_PLAYING)
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "media_player.turns_off",
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

    # Turn off - should trigger
    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Already off - should not trigger
    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_playing_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the playing trigger fires when a media player starts playing."""
    entity_id = "media_player.test"
    await async_setup_component(hass, "media_player", {})

    # Set initial state to idle
    hass.states.async_set(entity_id, STATE_IDLE)
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "media_player.playing",
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

    # Start playing - should trigger
    hass.states.async_set(entity_id, STATE_PLAYING)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Pause then play again - should trigger
    hass.states.async_set(entity_id, STATE_PAUSED)
    await hass.async_block_till_done()
    hass.states.async_set(entity_id, STATE_PLAYING)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id


async def test_playing_trigger_with_media_content_type_filter(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the playing trigger with media content type filter."""
    entity_id = "media_player.test"
    await async_setup_component(hass, "media_player", {})

    # Set initial state to idle
    hass.states.async_set(entity_id, STATE_IDLE)
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "media_player.playing",
                    "target": {
                        CONF_ENTITY_ID: entity_id,
                    },
                    "options": {
                        "media_content_type": ["music", "video"],
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

    # Start playing music - should trigger
    hass.states.async_set(
        entity_id, STATE_PLAYING, {ATTR_MEDIA_CONTENT_TYPE: "music"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Stop and play video - should trigger
    hass.states.async_set(entity_id, STATE_IDLE)
    await hass.async_block_till_done()
    hass.states.async_set(
        entity_id, STATE_PLAYING, {ATTR_MEDIA_CONTENT_TYPE: "video"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Stop and play podcast - should not trigger (not in filter)
    hass.states.async_set(entity_id, STATE_IDLE)
    await hass.async_block_till_done()
    hass.states.async_set(
        entity_id, STATE_PLAYING, {ATTR_MEDIA_CONTENT_TYPE: "podcast"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0
