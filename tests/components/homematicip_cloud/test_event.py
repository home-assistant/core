"""Tests for the HomematicIP Cloud event."""

from homematicip.base.channel_event import ChannelEvent

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .helper import HomeFactory, get_and_check_entity_basics


async def test_door_bell_event(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
) -> None:
    """Test of door bell event of HmIP-DSD-PCB."""
    entity_id = "event.dsdpcb_klingel_doorbell"
    entity_name = "dsdpcb_klingel doorbell"
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

    ha_state = hass.states.get(entity_id)
    assert ha_state.state != STATE_UNKNOWN


async def test_door_bell_event_wrong_event_type(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
) -> None:
    """Test of door bell event of HmIP-DSD-PCB."""
    entity_id = "event.dsdpcb_klingel_doorbell"
    entity_name = "dsdpcb_klingel doorbell"
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

    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_UNKNOWN
