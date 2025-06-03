"""Tests for the Sonos Alarm switch platform."""

from copy import copy
from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.sonos.const import DATA_SONOS_DISCOVERY_MANAGER
from homeassistant.components.sonos.switch import (
    ATTR_DURATION,
    ATTR_ID,
    ATTR_INCLUDE_LINKED_ZONES,
    ATTR_PLAY_MODE,
    ATTR_RECURRENCE,
    ATTR_VOLUME,
)
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import ATTR_TIME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import SonosMockEvent

from tests.common import async_fire_time_changed


async def test_entity_registry(
    hass: HomeAssistant, async_autosetup_sonos, entity_registry: er.EntityRegistry
) -> None:
    """Test sonos device with alarm registered in the device registry."""
    assert "media_player.zone_a" in entity_registry.entities
    assert "switch.sonos_alarm_14" in entity_registry.entities
    assert "switch.zone_a_status_light" in entity_registry.entities
    assert "switch.zone_a_loudness" in entity_registry.entities
    assert "switch.zone_a_night_sound" in entity_registry.entities
    assert "switch.zone_a_speech_enhancement" in entity_registry.entities
    assert "switch.zone_a_subwoofer_enabled" in entity_registry.entities
    assert "switch.zone_a_surround_enabled" in entity_registry.entities
    assert "switch.zone_a_touch_controls" in entity_registry.entities


async def test_switch_attributes(
    hass: HomeAssistant,
    async_autosetup_sonos,
    soco,
    fire_zgs_event,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for correct Sonos switch states."""
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

    surround_music_full_volume = entity_registry.entities[
        "switch.zone_a_surround_music_full_volume"
    ]
    surround_music_full_volume_state = hass.states.get(
        surround_music_full_volume.entity_id
    )
    assert surround_music_full_volume_state.state == STATE_ON

    night_sound = entity_registry.entities["switch.zone_a_night_sound"]
    night_sound_state = hass.states.get(night_sound.entity_id)
    assert night_sound_state.state == STATE_ON

    loudness = entity_registry.entities["switch.zone_a_loudness"]
    loudness_state = hass.states.get(loudness.entity_id)
    assert loudness_state.state == STATE_ON

    speech_enhancement = entity_registry.entities["switch.zone_a_speech_enhancement"]
    speech_enhancement_state = hass.states.get(speech_enhancement.entity_id)
    assert speech_enhancement_state.state == STATE_ON

    crossfade = entity_registry.entities["switch.zone_a_crossfade"]
    crossfade_state = hass.states.get(crossfade.entity_id)
    assert crossfade_state.state == STATE_ON

    # Ensure switches are disabled
    status_light = entity_registry.entities["switch.zone_a_status_light"]
    assert hass.states.get(status_light.entity_id) is None

    touch_controls = entity_registry.entities["switch.zone_a_touch_controls"]
    assert hass.states.get(touch_controls.entity_id) is None

    sub_switch = entity_registry.entities["switch.zone_a_subwoofer_enabled"]
    sub_switch_state = hass.states.get(sub_switch.entity_id)
    assert sub_switch_state.state == STATE_OFF

    surround_switch = entity_registry.entities["switch.zone_a_surround_enabled"]
    surround_switch_state = hass.states.get(surround_switch.entity_id)
    assert surround_switch_state.state == STATE_ON

    # Enable disabled switches
    for entity in (status_light, touch_controls):
        entity_registry.async_update_entity(
            entity_id=entity.entity_id, disabled_by=None
        )
    await hass.async_block_till_done()

    # Fire event to cancel poll timer and avoid triggering errors during time jump
    service = soco.contentDirectory
    empty_event = SonosMockEvent(soco, service, {})
    subscription = service.subscribe.return_value
    subscription.callback(event=empty_event)
    await hass.async_block_till_done()

    # Mock shutdown calls during config entry reload
    with patch.object(hass.data[DATA_SONOS_DISCOVERY_MANAGER], "async_shutdown") as m:
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        assert m.called

    # Trigger subscription callback for speaker discovery
    await fire_zgs_event()
    await hass.async_block_till_done(wait_background_tasks=True)

    status_light_state = hass.states.get(status_light.entity_id)
    assert status_light_state.state == STATE_ON

    touch_controls = entity_registry.entities["switch.zone_a_touch_controls"]
    touch_controls_state = hass.states.get(touch_controls.entity_id)
    assert touch_controls_state.state == STATE_ON


async def test_alarm_create_delete(
    hass: HomeAssistant,
    async_setup_sonos,
    soco,
    alarm_clock,
    alarm_clock_extended,
    alarm_event,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for correct creation and deletion of alarms during runtime."""
    one_alarm = copy(alarm_clock.ListAlarms.return_value)
    two_alarms = copy(alarm_clock_extended.ListAlarms.return_value)

    await async_setup_sonos()

    assert "switch.sonos_alarm_14" in entity_registry.entities
    assert "switch.sonos_alarm_15" not in entity_registry.entities

    subscription = alarm_clock.subscribe.return_value
    sub_callback = subscription.callback

    alarm_clock.ListAlarms.return_value = two_alarms

    alarm_event.variables["alarm_list_version"] = two_alarms["CurrentAlarmListVersion"]

    sub_callback(event=alarm_event)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "switch.sonos_alarm_14" in entity_registry.entities
    assert "switch.sonos_alarm_15" in entity_registry.entities

    one_alarm["CurrentAlarmListVersion"] = alarm_event.increment_variable(
        "alarm_list_version"
    )

    alarm_clock.ListAlarms.return_value = one_alarm

    sub_callback(event=alarm_event)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "switch.sonos_alarm_14" in entity_registry.entities
    assert "switch.sonos_alarm_15" not in entity_registry.entities
