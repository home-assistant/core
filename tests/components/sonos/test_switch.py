"""Tests for the Sonos Alarm switch platform."""
from copy import copy

from homeassistant.components.sonos import DOMAIN
from homeassistant.components.sonos.switch import (
    ATTR_DURATION,
    ATTR_ID,
    ATTR_INCLUDE_LINKED_ZONES,
    ATTR_PLAY_MODE,
    ATTR_RECURRENCE,
    ATTR_VOLUME,
)
from homeassistant.const import ATTR_TIME, STATE_ON
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.setup import async_setup_component


async def setup_platform(hass, config_entry, config):
    """Set up the switch platform for testing."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_entity_registry(hass, config_entry, config):
    """Test sonos device with alarm registered in the device registry."""
    await setup_platform(hass, config_entry, config)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    assert "media_player.zone_a" in entity_registry.entities
    assert "switch.sonos_alarm_14" in entity_registry.entities
    assert "switch.sonos_zone_a_status_light" in entity_registry.entities
    assert "switch.sonos_zone_a_night_sound" in entity_registry.entities
    assert "switch.sonos_zone_a_speech_enhancement" in entity_registry.entities
    assert "switch.sonos_zone_a_touch_controls" in entity_registry.entities


async def test_switch_attributes(hass, config_entry, config, soco):
    """Test for correct Sonos switch states."""
    await setup_platform(hass, config_entry, config)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    alarm = entity_registry.entities["switch.sonos_alarm_14"]
    alarm_state = hass.states.get(alarm.entity_id)
    assert alarm_state.state == STATE_ON
    assert alarm_state.attributes.get(ATTR_TIME) == "07:00:00"
    assert alarm_state.attributes.get(ATTR_ID) == "14"
    assert alarm_state.attributes.get(ATTR_DURATION) == "02:00:00"
    assert alarm_state.attributes.get(ATTR_RECURRENCE) == "DAILY"
    assert alarm_state.attributes.get(ATTR_VOLUME) == 0.25
    assert alarm_state.attributes.get(ATTR_PLAY_MODE) == "SHUFFLE_NOREPEAT"
    assert not alarm_state.attributes.get(ATTR_INCLUDE_LINKED_ZONES)

    night_sound = entity_registry.entities["switch.sonos_zone_a_night_sound"]
    night_sound_state = hass.states.get(night_sound.entity_id)
    assert night_sound_state.state == STATE_ON

    speech_enhancement = entity_registry.entities[
        "switch.sonos_zone_a_speech_enhancement"
    ]
    speech_enhancement_state = hass.states.get(speech_enhancement.entity_id)
    assert speech_enhancement_state.state == STATE_ON

    crossfade = entity_registry.entities["switch.sonos_zone_a_crossfade"]
    crossfade_state = hass.states.get(crossfade.entity_id)
    assert crossfade_state.state == STATE_ON

    status_light = entity_registry.entities["switch.sonos_zone_a_status_light"]
    status_light_state = hass.states.get(status_light.entity_id)
    assert status_light_state.state == STATE_ON

    touch_controls = entity_registry.entities["switch.sonos_zone_a_touch_controls"]
    touch_controls_state = hass.states.get(touch_controls.entity_id)
    assert touch_controls_state.state == STATE_ON


async def test_alarm_create_delete(
    hass, config_entry, config, soco, alarm_clock, alarm_clock_extended, alarm_event
):
    """Test for correct creation and deletion of alarms during runtime."""
    entity_registry = async_get_entity_registry(hass)

    one_alarm = copy(alarm_clock.ListAlarms.return_value)
    two_alarms = copy(alarm_clock_extended.ListAlarms.return_value)

    await setup_platform(hass, config_entry, config)

    assert "switch.sonos_alarm_14" in entity_registry.entities
    assert "switch.sonos_alarm_15" not in entity_registry.entities

    subscription = alarm_clock.subscribe.return_value
    sub_callback = subscription.callback

    alarm_clock.ListAlarms.return_value = two_alarms

    alarm_event.variables["alarm_list_version"] = two_alarms["CurrentAlarmListVersion"]

    sub_callback(event=alarm_event)
    await hass.async_block_till_done()

    assert "switch.sonos_alarm_14" in entity_registry.entities
    assert "switch.sonos_alarm_15" in entity_registry.entities

    one_alarm["CurrentAlarmListVersion"] = alarm_event.increment_variable(
        "alarm_list_version"
    )

    alarm_clock.ListAlarms.return_value = one_alarm

    sub_callback(event=alarm_event)
    await hass.async_block_till_done()

    assert "switch.sonos_alarm_14" in entity_registry.entities
    assert "switch.sonos_alarm_15" not in entity_registry.entities
