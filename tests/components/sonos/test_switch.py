"""Tests for the Sonos Alarm switch platform."""

from copy import copy
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from soco.exceptions import SoCoException, SoCoUPnPException

from homeassistant.components.sonos import DOMAIN
from homeassistant.components.sonos.const import (
    DATA_SONOS_DISCOVERY_MANAGER,
    MODEL_SONOS_ARC_ULTRA,
)
from homeassistant.components.sonos.switch import (
    ATTR_DURATION,
    ATTR_ID,
    ATTR_INCLUDE_LINKED_ZONES,
    ATTR_PLAY_MODE,
    ATTR_RECURRENCE,
    ATTR_SPEECH_ENHANCEMENT,
    ATTR_SPEECH_ENHANCEMENT_ENABLED,
    ATTR_TV_AUTOPLAY,
    ATTR_TV_UNGROUP_AUTOPLAY,
    ATTR_VOLUME,
)
from homeassistant.components.ssdp import SsdpChange
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TIME,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.service_info.ssdp import ATTR_UPNP_UDN, SsdpServiceInfo
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import (
    MockSoCo,
    SoCoMockFactory,
    SonosMockEvent,
    SonosMockService,
    create_rendering_control_event,
)

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


@pytest.mark.parametrize(
    ("model", "attribute"),
    [
        ("Sonos One SL", ATTR_SPEECH_ENHANCEMENT),
        (MODEL_SONOS_ARC_ULTRA.lower(), ATTR_SPEECH_ENHANCEMENT_ENABLED),
    ],
)
async def test_switch_speech_enhancement(
    hass: HomeAssistant,
    async_setup_sonos,
    soco: MockSoCo,
    speaker_info: dict[str, str],
    entity_registry: er.EntityRegistry,
    model: str,
    attribute: str,
) -> None:
    """Tests the speech enhancement switch and attribute substitution for different models."""
    entity_id = "switch.zone_a_speech_enhancement"
    speaker_info["model_name"] = model
    soco.get_speaker_info.return_value = speaker_info
    setattr(soco, attribute, True)
    await async_setup_sonos()
    switch = entity_registry.entities[entity_id]
    state = hass.states.get(switch.entity_id)
    assert state.state == STATE_ON

    event = create_rendering_control_event(soco)
    event.variables[attribute] = False
    soco.renderingControl.subscribe.return_value._callback(event)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(switch.entity_id)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert getattr(soco, attribute) is True


@pytest.mark.parametrize(
    ("service", "expected_result"),
    [
        (SERVICE_TURN_OFF, "0"),
        (SERVICE_TURN_ON, "1"),
    ],
)
async def test_switch_alarm_turn_on(
    hass: HomeAssistant,
    async_setup_sonos,
    soco: MockSoCo,
    service: str,
    expected_result: str,
) -> None:
    """Test enabling and disabling of alarm."""
    await async_setup_sonos()

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: "switch.sonos_alarm_14"}, blocking=True
    )

    assert soco.alarmClock.UpdateAlarm.call_count == 1
    call_args = soco.alarmClock.UpdateAlarm.call_args[0]
    assert call_args[0][0] == ("ID", "14")
    assert call_args[0][4] == ("Enabled", expected_result)


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


async def test_alarm_change_device(
    hass: HomeAssistant,
    alarm_clock: SonosMockService,
    alarm_clock_extended: SonosMockService,
    alarm_event: SonosMockEvent,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    soco_factory: SoCoMockFactory,
) -> None:
    """Test Sonos Alarm being moved to a different speaker.

    This test simulates a scenario where an alarm is created on one speaker
    and then moved to another speaker. It checks that the entity is correctly
    created on the new speaker and removed from the old one.
    """

    # Create the alarm on the soco_lr speaker
    soco_factory.mock_zones = True
    soco_lr = soco_factory.cache_mock(MockSoCo(), "10.10.10.1", "Living Room")
    alarm_dict = copy(alarm_clock.ListAlarms.return_value)
    alarm_dict["CurrentAlarmList"] = alarm_dict["CurrentAlarmList"].replace(
        "RINCON_test", f"{soco_lr.uid}"
    )
    alarm_dict["CurrentAlarmListVersion"] = "RINCON_test:900"
    soco_lr.alarmClock.ListAlarms.return_value = alarm_dict
    soco_br = soco_factory.cache_mock(MockSoCo(), "10.10.10.2", "Bedroom")
    await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "media_player": {
                    "interface_addr": "127.0.0.1",
                    "hosts": ["10.10.10.1", "10.10.10.2"],
                }
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "switch.sonos_alarm_14"

    # Verify the alarm is created on the soco_lr speaker
    assert entity_id in entity_registry.entities
    entity = entity_registry.async_get(entity_id)
    device = device_registry.async_get(entity.device_id)
    assert device.name == soco_lr.get_speaker_info()["zone_name"]

    # Simulate the alarm being moved to the soco_br speaker
    alarm_update = copy(alarm_clock_extended.ListAlarms.return_value)
    alarm_update["CurrentAlarmList"] = alarm_update["CurrentAlarmList"].replace(
        "RINCON_test", f"{soco_br.uid}"
    )
    alarm_clock.ListAlarms.return_value = alarm_update

    # Update the alarm_list_version so it gets processed.
    alarm_event.variables["alarm_list_version"] = "RINCON_test:1000"
    alarm_update["CurrentAlarmListVersion"] = alarm_event.increment_variable(
        "alarm_list_version"
    )

    alarm_clock.subscribe.return_value.callback(event=alarm_event)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entity_id in entity_registry.entities
    alarm_14 = entity_registry.async_get(entity_id)
    device = device_registry.async_get(alarm_14.device_id)
    assert device.name == soco_br.get_speaker_info()["zone_name"]


async def test_tv_autoplay_switch(
    hass: HomeAssistant,
    async_setup_sonos,
    soco: MockSoCo,
    speaker_info: dict[str, str],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test TV autoplay switch creation, state and turn on/off for HT devices."""
    entity_id = f"switch.zone_a_{ATTR_TV_AUTOPLAY}"

    speaker_info["model_name"] = "Sonos Beam"
    soco.get_speaker_info.return_value = speaker_info
    soco.deviceProperties.GetAutoplayRoomUUID = Mock(
        return_value={"RoomUUID": soco.uid, "Source": "TV"}
    )
    await async_setup_sonos()

    assert entity_registry.entities.get(entity_id) is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    # Turn off: should call SetAutoplayRoomUUID with empty RoomUUID
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    soco.deviceProperties.SetAutoplayRoomUUID.assert_called_once_with(
        [("RoomUUID", ""), ("Source", "TV")]
    )
    soco.deviceProperties.SetAutoplayRoomUUID.reset_mock()

    # Turn on: should call SetAutoplayRoomUUID with speaker's own UID
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    soco.deviceProperties.SetAutoplayRoomUUID.assert_called_once_with(
        [("RoomUUID", soco.uid), ("Source", "TV")]
    )


async def test_tv_autoplay_poll_state(
    hass: HomeAssistant,
    async_setup_sonos,
    soco: MockSoCo,
    speaker_info: dict[str, str],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that TV autoplay switch polls state from device."""
    entity_id = f"switch.zone_a_{ATTR_TV_AUTOPLAY}"

    speaker_info["model_name"] = "Sonos Beam"
    soco.get_speaker_info.return_value = speaker_info
    soco.deviceProperties.GetAutoplayRoomUUID = Mock(
        return_value={"RoomUUID": "", "Source": "TV"}
    )
    await async_setup_sonos()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    # Simulate poll returning enabled
    soco.deviceProperties.GetAutoplayRoomUUID = Mock(
        return_value={"RoomUUID": soco.uid, "Source": "TV"}
    )
    await async_update_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_tv_autoplay_not_created_for_non_ht(
    hass: HomeAssistant,
    async_autosetup_sonos,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that TV autoplay switch is not created when device raises SoCoUPnPException.

    Non-HT devices don't support the GetAutoplayRoomUUID action and raise
    SoCoUPnPException, which is the capability check we rely on. The conftest
    mock raises SoCoUPnPException by default to simulate non-HT devices.
    """
    entity_id = f"switch.zone_a_{ATTR_TV_AUTOPLAY}"
    assert entity_id not in entity_registry.entities


async def test_tv_autoplay_toggle_failure_raises(
    hass: HomeAssistant,
    async_setup_sonos,
    soco: MockSoCo,
    speaker_info: dict[str, str],
) -> None:
    """Test that HomeAssistantError is raised when TV autoplay toggle fails."""
    entity_id = f"switch.zone_a_{ATTR_TV_AUTOPLAY}"

    speaker_info["model_name"] = "Sonos Beam"
    soco.get_speaker_info.return_value = speaker_info
    soco.deviceProperties.GetAutoplayRoomUUID = Mock(
        return_value={"RoomUUID": "", "Source": "TV"}
    )
    await async_setup_sonos()

    soco.deviceProperties.SetAutoplayRoomUUID = Mock(
        side_effect=SoCoUPnPException("Toggle failed", 500, "")
    )
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


async def test_tv_ungroup_autoplay_switch(
    hass: HomeAssistant,
    async_setup_sonos,
    soco: MockSoCo,
    speaker_info: dict[str, str],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test ungroup-on-autoplay switch creation, state and turn on/off."""
    entity_id = f"switch.zone_a_{ATTR_TV_UNGROUP_AUTOPLAY}"

    speaker_info["model_name"] = "Sonos Beam"
    soco.get_speaker_info.return_value = speaker_info
    soco.deviceProperties.GetAutoplayRoomUUID = Mock(
        return_value={"RoomUUID": soco.uid, "Source": "TV"}
    )
    # IncludeLinkedZones=0 means "don't include linked zones" = ungroup = ON
    soco.deviceProperties.GetAutoplayLinkedZones = Mock(
        return_value={"IncludeLinkedZones": "0", "Source": "TV"}
    )
    await async_setup_sonos()

    assert entity_registry.entities.get(entity_id) is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    # Turn off: should send IncludeLinkedZones=1 (include group = stop ungrouping)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    soco.deviceProperties.SetAutoplayLinkedZones.assert_called_once_with(
        [("IncludeLinkedZones", "1"), ("Source", "TV")]
    )
    soco.deviceProperties.SetAutoplayLinkedZones.reset_mock()

    # Turn on: should send IncludeLinkedZones=0 (don't include group = ungroup)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    soco.deviceProperties.SetAutoplayLinkedZones.assert_called_once_with(
        [("IncludeLinkedZones", "0"), ("Source", "TV")]
    )


async def test_tv_ungroup_autoplay_available_independently_of_tv_autoplay(
    hass: HomeAssistant,
    async_setup_sonos,
    soco: MockSoCo,
    speaker_info: dict[str, str],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test ungroup-on-autoplay reflects device state regardless of TV autoplay state.

    The device manages the dependency between the two settings. HA should poll
    the actual device value and not force the switch unavailable or off.
    """
    ungroup_id = f"switch.zone_a_{ATTR_TV_UNGROUP_AUTOPLAY}"

    speaker_info["model_name"] = "Sonos Beam"
    soco.get_speaker_info.return_value = speaker_info
    # TV autoplay is disabled — the scenario we're testing
    soco.deviceProperties.GetAutoplayRoomUUID = Mock(
        return_value={"RoomUUID": "", "Source": "TV"}
    )
    # IncludeLinkedZones=0 means ungroup = ON, even when TV autoplay is disabled.
    soco.deviceProperties.GetAutoplayLinkedZones = Mock(
        return_value={"IncludeLinkedZones": "0", "Source": "TV"}
    )
    await async_setup_sonos()

    state = hass.states.get(ungroup_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.state != STATE_UNAVAILABLE

    # Simulate the device reporting ungroup as off while TV autoplay remains
    # disabled. The switch should show OFF, not unavailable.
    soco.deviceProperties.GetAutoplayRoomUUID = Mock(
        return_value={"RoomUUID": "", "Source": "TV"}
    )
    soco.deviceProperties.GetAutoplayLinkedZones = Mock(
        return_value={"IncludeLinkedZones": "1", "Source": "TV"}
    )
    await async_update_entity(hass, ungroup_id)

    state = hass.states.get(ungroup_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.state != STATE_UNAVAILABLE


async def test_tv_ungroup_autoplay_unavailable_when_linked_zones_missing(
    hass: HomeAssistant,
    async_setup_sonos,
    soco: MockSoCo,
    speaker_info: dict[str, str],
) -> None:
    """Test ungroup-on-autoplay becomes unavailable when IncludeLinkedZones is absent."""
    entity_id = f"switch.zone_a_{ATTR_TV_UNGROUP_AUTOPLAY}"

    speaker_info["model_name"] = "Sonos Beam"
    soco.get_speaker_info.return_value = speaker_info
    soco.deviceProperties.GetAutoplayRoomUUID = Mock(
        return_value={"RoomUUID": soco.uid, "Source": "TV"}
    )
    soco.deviceProperties.GetAutoplayLinkedZones = Mock(
        return_value={"IncludeLinkedZones": "0", "Source": "TV"}
    )
    await async_setup_sonos()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    # Simulate a poll where the response is missing IncludeLinkedZones
    soco.deviceProperties.GetAutoplayLinkedZones = Mock(return_value={"Source": "TV"})
    await async_update_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_tv_ungroup_autoplay_toggle_failure_raises(
    hass: HomeAssistant,
    async_setup_sonos,
    soco: MockSoCo,
    speaker_info: dict[str, str],
) -> None:
    """Test that HomeAssistantError is raised when ungroup-on-autoplay toggle fails."""
    entity_id = f"switch.zone_a_{ATTR_TV_UNGROUP_AUTOPLAY}"

    speaker_info["model_name"] = "Sonos Beam"
    soco.get_speaker_info.return_value = speaker_info
    soco.deviceProperties.GetAutoplayRoomUUID = Mock(
        return_value={"RoomUUID": soco.uid, "Source": "TV"}
    )
    soco.deviceProperties.GetAutoplayLinkedZones = Mock(
        return_value={"IncludeLinkedZones": "0", "Source": "TV"}
    )
    await async_setup_sonos()

    soco.deviceProperties.SetAutoplayLinkedZones = Mock(
        side_effect=SoCoUPnPException("Toggle failed", 500, "")
    )
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


async def test_tv_ungroup_autoplay_not_created_for_non_ht(
    hass: HomeAssistant,
    async_autosetup_sonos,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that ungroup-on-autoplay switch is not created when device raises SoCoUPnPException.

    Non-HT devices don't support the GetAutoplayLinkedZones action and raise
    SoCoUPnPException, which is the capability check we rely on. The conftest
    mock raises SoCoUPnPException by default to simulate non-HT devices.
    """
    entity_id = f"switch.zone_a_{ATTR_TV_UNGROUP_AUTOPLAY}"
    assert entity_id not in entity_registry.entities


async def test_alarm_update_exception_logs_warning(
    hass: HomeAssistant,
    async_setup_sonos,
    entity_registry: er.EntityRegistry,
    soco: MockSoCo,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test household mismatch logs warning and alarm update/setup is skipped."""
    with patch(
        "homeassistant.components.sonos.alarms.Alarms.update",
        side_effect=SoCoException(
            "Alarm list UID RINCON_0001234567890:31 does not match RINCON_000E987654321:0"
        ),
    ):
        await async_setup_sonos()
        await hass.async_block_till_done()

    # Alarm should not be set up due to household mismatch
    assert "switch.sonos_alarm_14" not in entity_registry.entities
    assert "cannot be updated due to a household mismatch" in caplog.text


async def test_alarm_setup_for_undiscovered_speaker(
    hass: HomeAssistant,
    async_setup_sonos,
    alarm_clock,
    entity_registry: er.EntityRegistry,
    soco_factory: SoCoMockFactory,
    discover,
) -> None:
    """Test for creation of alarm on a speaker that is discovered after the integration is setup."""

    soco_bedroom = soco_factory.cache_mock(MockSoCo(), "10.10.10.2", "Bedroom")
    one_alarm = copy(alarm_clock.ListAlarms.return_value)
    one_alarm["CurrentAlarmList"] = one_alarm["CurrentAlarmList"].replace(
        "RINCON_test", soco_bedroom.uid
    )
    alarm_clock.ListAlarms.return_value = one_alarm
    await async_setup_sonos()

    # Switch should not be created since the speaker isn't discovered yet
    assert "switch.sonos_alarm_14" not in entity_registry.entities

    # Simulate discovery of the bedroom speaker
    discover.call_args.args[1](
        SsdpServiceInfo(
            ssdp_location=f"http://{soco_bedroom.ip_address}/",
            ssdp_st="urn:schemas-upnp-org:device:ZonePlayer:1",
            ssdp_usn=f"uuid:{soco_bedroom.uid}_MR::urn:schemas-upnp-org:service:GroupRenderingControl:1",
            upnp={ATTR_UPNP_UDN: f"uuid:{soco_bedroom.uid}"},
        ),
        SsdpChange.ALIVE,
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "switch.sonos_alarm_14" in entity_registry.entities
