"""Tests for the HomematicIP Cloud event."""

from homematicip.base.channel_event import ChannelEvent
import pytest

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .helper import HomeFactory, get_and_check_entity_basics


async def test_door_bell_event(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
) -> None:
    """Test of door bell event of HmIP-DSD-PCB."""
    entity_id = "event.dsdpcb_klingel_doorbell"
    entity_name = "dsdpcb_klingel Doorbell"
    device_model = "HmIP-DSD-PCB"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["dsdpcb_klingel"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    ch = hmip_device.functionalChannels[1]
    channel_event = ChannelEvent(
        channelEventType="DOOR_BELL_SENSOR_EVENT", channelIndex=1, deviceId=ch.device.id
    )

    assert ha_state.state == STATE_UNKNOWN

    ch.fire_channel_event(channel_event)
    await hass.async_block_till_done()

    ha_state = hass.states.get(entity_id)
    assert ha_state.state != STATE_UNKNOWN


async def test_door_bell_event_wrong_event_type(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
) -> None:
    """Test of door bell event of HmIP-DSD-PCB."""
    entity_id = "event.dsdpcb_klingel_doorbell"
    entity_name = "dsdpcb_klingel Doorbell"
    device_model = "HmIP-DSD-PCB"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["dsdpcb_klingel"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    ch = hmip_device.functionalChannels[1]
    channel_event = ChannelEvent(
        channelEventType="KEY_PRESS", channelIndex=1, deviceId=ch.device.id
    )

    assert ha_state.state == STATE_UNKNOWN

    ch.fire_channel_event(channel_event)
    await hass.async_block_till_done()

    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("raw_event", "expected_state"),
    [
        ("KEY_PRESS_SHORT", "short_release"),
        ("KEY_PRESS_LONG_START", "long_press"),
        ("KEY_PRESS_LONG_STOP", "long_release"),
    ],
)
async def test_wrc6_button_event(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
    raw_event: str,
    expected_state: str,
) -> None:
    """Test per-button event entities on HmIP-WRC6."""
    entity_id = "event.wandtaster_6_fach_button_3"
    entity_name = "Wandtaster - 6-fach Button 3"
    device_model = "HmIP-WRC6"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Wandtaster - 6-fach"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_UNKNOWN

    ch = next(c for c in hmip_device.functionalChannels if c.index == 3)
    ch.fire_channel_event(
        ChannelEvent(channelEventType=raw_event, channelIndex=3, deviceId=ch.device.id)
    )
    await hass.async_block_till_done()

    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes["event_type"] == expected_state


async def test_wrc6_button_ignores_repeating_long(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
) -> None:
    """KEY_PRESS_LONG (the repeating tick) must not change the entity state.

    Fire a recognized event first so the entity advances past STATE_UNKNOWN,
    then fire KEY_PRESS_LONG and assert nothing about the entity changed.
    """
    entity_id = "event.wandtaster_6_fach_button_3"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Wandtaster - 6-fach"]
    )

    hmip_device = mock_hap.hmip_device_by_entity_id[entity_id]
    ch = next(c for c in hmip_device.functionalChannels if c.index == 3)

    ch.fire_channel_event(
        ChannelEvent(
            channelEventType="KEY_PRESS_SHORT", channelIndex=3, deviceId=ch.device.id
        )
    )
    await hass.async_block_till_done()
    state_after_short = hass.states.get(entity_id)
    assert state_after_short.state != STATE_UNKNOWN
    assert state_after_short.attributes["event_type"] == "short_release"

    ch.fire_channel_event(
        ChannelEvent(
            channelEventType="KEY_PRESS_LONG", channelIndex=3, deviceId=ch.device.id
        )
    )
    await hass.async_block_till_done()
    state_after_long = hass.states.get(entity_id)
    assert state_after_long.state == state_after_short.state
    assert state_after_long.attributes["event_type"] == "short_release"
