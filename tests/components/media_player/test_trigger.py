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


async def test_paused_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the paused trigger fires when a media player pauses."""
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
                    "trigger": "media_player.paused",
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

    # Pause - should trigger
    hass.states.async_set(entity_id, STATE_PAUSED)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Already paused - should not trigger
    hass.states.async_set(entity_id, STATE_PAUSED)
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_stopped_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the stopped trigger fires when a media player stops playing."""
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
                    "trigger": "media_player.stopped",
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

    # Stop to idle - should trigger
    hass.states.async_set(entity_id, STATE_IDLE)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Start playing again and then stop to off - should trigger
    hass.states.async_set(entity_id, STATE_PLAYING)
    await hass.async_block_till_done()
    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Stop from paused - should trigger
    hass.states.async_set(entity_id, STATE_PLAYING)
    await hass.async_block_till_done()
    hass.states.async_set(entity_id, STATE_PAUSED)
    await hass.async_block_till_done()
    hass.states.async_set(entity_id, STATE_IDLE)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id


async def test_muted_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the muted trigger fires when a media player gets muted."""
    entity_id = "media_player.test"
    await async_setup_component(hass, "media_player", {})

    # Set initial state with volume unmuted
    from homeassistant.components.media_player import ATTR_MEDIA_VOLUME_MUTED
    hass.states.async_set(entity_id, STATE_PLAYING, {ATTR_MEDIA_VOLUME_MUTED: False})
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "media_player.muted",
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

    # Mute - should trigger
    hass.states.async_set(entity_id, STATE_PLAYING, {ATTR_MEDIA_VOLUME_MUTED: True})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Already muted - should not trigger
    hass.states.async_set(entity_id, STATE_PLAYING, {ATTR_MEDIA_VOLUME_MUTED: True})
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_unmuted_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the unmuted trigger fires when a media player gets unmuted."""
    entity_id = "media_player.test"
    await async_setup_component(hass, "media_player", {})

    # Set initial state with volume muted
    from homeassistant.components.media_player import ATTR_MEDIA_VOLUME_MUTED
    hass.states.async_set(entity_id, STATE_PLAYING, {ATTR_MEDIA_VOLUME_MUTED: True})
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "media_player.unmuted",
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

    # Unmute - should trigger
    hass.states.async_set(entity_id, STATE_PLAYING, {ATTR_MEDIA_VOLUME_MUTED: False})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Already unmuted - should not trigger
    hass.states.async_set(entity_id, STATE_PLAYING, {ATTR_MEDIA_VOLUME_MUTED: False})
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_volume_changed_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the volume changed trigger fires when volume changes."""
    entity_id = "media_player.test"
    await async_setup_component(hass, "media_player", {})

    # Set initial state with volume
    from homeassistant.components.media_player import ATTR_MEDIA_VOLUME_LEVEL
    hass.states.async_set(entity_id, STATE_PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 0.5})
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "media_player.volume_changed",
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

    # Change volume - should trigger
    hass.states.async_set(entity_id, STATE_PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 0.7})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Same volume - should not trigger
    hass.states.async_set(entity_id, STATE_PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 0.7})
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_volume_changed_trigger_with_above_threshold(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the volume changed trigger with above threshold."""
    entity_id = "media_player.test"
    await async_setup_component(hass, "media_player", {})

    # Set initial state with volume
    from homeassistant.components.media_player import ATTR_MEDIA_VOLUME_LEVEL
    hass.states.async_set(entity_id, STATE_PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 0.3})
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "media_player.volume_changed",
                    "target": {CONF_ENTITY_ID: entity_id},
                    "options": {
                        "above": 0.5,
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

    # Change volume above threshold - should trigger
    hass.states.async_set(entity_id, STATE_PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 0.7})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Change volume but still below threshold - should not trigger
    hass.states.async_set(entity_id, STATE_PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 0.4})
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_volume_changed_trigger_with_below_threshold(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the volume changed trigger with below threshold."""
    entity_id = "media_player.test"
    await async_setup_component(hass, "media_player", {})

    # Set initial state with volume
    from homeassistant.components.media_player import ATTR_MEDIA_VOLUME_LEVEL
    hass.states.async_set(entity_id, STATE_PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 0.7})
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "media_player.volume_changed",
                    "target": {CONF_ENTITY_ID: entity_id},
                    "options": {
                        "below": 0.5,
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

    # Change volume below threshold - should trigger
    hass.states.async_set(entity_id, STATE_PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 0.3})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Change volume but still above threshold - should not trigger
    hass.states.async_set(entity_id, STATE_PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 0.6})
    await hass.async_block_till_done()
    assert len(service_calls) == 0
