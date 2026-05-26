"""Support for HomematicIP Cloud events."""

from collections.abc import Callable
from dataclasses import dataclass

from homematicip.base.channel_event import ChannelEvent
from homematicip.base.enums import FunctionalChannelType
from homematicip.base.functionalChannels import FunctionalChannel
from homematicip.device import Device

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HomematicipGenericEntity
from .hap import HomematicIPConfigEntry, HomematicipHAP


@dataclass(frozen=True, kw_only=True)
class HmipEventEntityDescription(EventEntityDescription):
    """Description of a HomematicIP Cloud event."""

    event_type_map: dict[str, str]
    channel_selector_fn: Callable[[FunctionalChannel], bool]
    is_multi_channel: bool = False


EVENT_DESCRIPTIONS: tuple[HmipEventEntityDescription, ...] = (
    HmipEventEntityDescription(
        key="doorbell",
        translation_key="doorbell",
        device_class=EventDeviceClass.DOORBELL,
        event_types=["ring"],
        event_type_map={"DOOR_BELL_SENSOR_EVENT": "ring"},
        channel_selector_fn=lambda channel: channel.channelRole == "DOOR_BELL_INPUT",
    ),
    # Button event types follow the standard names proposed in
    # home-assistant/architecture#1377: short_release, long_press,
    # long_release. HmIP doesn't expose a separate press-down ("initial_press")
    # event for short presses; KEY_PRESS_LONG_START is mapped to long_press
    # (no separate initial_press fires for the hold sequence either).
    HmipEventEntityDescription(
        key="button",
        translation_key="button",
        device_class=EventDeviceClass.BUTTON,
        event_types=["short_release", "long_press", "long_release"],
        event_type_map={
            "KEY_PRESS_SHORT": "short_release",
            "KEY_PRESS_LONG_START": "long_press",
            "KEY_PRESS_LONG_STOP": "long_release",
        },
        channel_selector_fn=lambda channel: (
            channel.functionalChannelType == FunctionalChannelType.SINGLE_KEY_CHANNEL
        ),
        is_multi_channel=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomematicIPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP events from a config entry."""
    hap = config_entry.runtime_data

    async_add_entities(
        HomematicipChannelEvent(hap, device, channel, description)
        for description in EVENT_DESCRIPTIONS
        for device in hap.home.devices
        for channel in device.functionalChannels
        if description.channel_selector_fn(channel)
    )


class HomematicipChannelEvent(HomematicipGenericEntity, EventEntity):
    """Event entity backed by a HomematicIP functional channel."""

    entity_description: HmipEventEntityDescription

    def __init__(
        self,
        hap: HomematicipHAP,
        device: Device,
        channel: FunctionalChannel,
        description: HmipEventEntityDescription,
    ) -> None:
        """Initialize the channel-backed event entity."""
        super().__init__(
            hap,
            device,
            channel=channel.index,
            channel_real_index=channel.index if description.is_multi_channel else None,
            is_multi_channel=description.is_multi_channel,
            feature_id=description.key,
            use_description_name=description.is_multi_channel,
        )
        self.entity_description = description
        if description.is_multi_channel:
            self._attr_translation_placeholders = {"channel": str(channel.index)}

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        channel = self.get_channel_or_raise()
        channel.add_on_channel_event_handler(self._async_handle_event)

    @callback
    def _async_handle_event(self, *args, **kwargs) -> None:
        """Handle the event fired by the functional channel."""
        raw_channel_event_type = self._get_channel_event_from_args(*args)
        public_event = self.entity_description.event_type_map.get(
            raw_channel_event_type
        )
        if public_event is None:
            return
        self._trigger_event(event_type=public_event)
        self.async_write_ha_state()

    def _get_channel_event_from_args(self, *args) -> str:
        """Get the channel event."""
        if isinstance(args[0], ChannelEvent):
            return args[0].channelEventType

        return ""
