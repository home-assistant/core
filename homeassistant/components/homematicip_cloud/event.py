"""Support for HomematicIP Cloud events."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homematicip.base.channel_event import ChannelEvent
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

    channel_event_types: list[str] | None = None
    channel_selector_fn: Callable[[FunctionalChannel], bool] | None = None


EVENT_DESCRIPTIONS = {
    "doorbell": HmipEventEntityDescription(
        key="doorbell",
        translation_key="doorbell",
        device_class=EventDeviceClass.DOORBELL,
        event_types=["ring"],
        channel_event_types=["DOOR_BELL_SENSOR_EVENT"],
        channel_selector_fn=lambda channel: channel.channelRole == "DOOR_BELL_INPUT",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomematicIPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP cover from a config entry."""
    hap = config_entry.runtime_data
    entities: list[HomematicipGenericEntity] = []

    entities.extend(
        HomematicipDoorBellEvent(
            hap,
            device,
            channel.index,
            description,
        )
        for description in EVENT_DESCRIPTIONS.values()
        for device in hap.home.devices
        for channel in device.functionalChannels
        if description.channel_selector_fn and description.channel_selector_fn(channel)
    )

    async_add_entities(entities)


class HomematicipDoorBellEvent(HomematicipGenericEntity, EventEntity):
    """Event class for HomematicIP doorbell events."""

    _attr_device_class = EventDeviceClass.DOORBELL
    entity_description: HmipEventEntityDescription

    def __init__(
        self,
        hap: HomematicipHAP,
        device: Device,
        channel: int,
        description: HmipEventEntityDescription,
    ) -> None:
        """Initialize the event."""
        super().__init__(
            hap,
            device,
            post=description.key,
            channel=channel,
            is_multi_channel=False,
        )

        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.functional_channel.add_on_channel_event_handler(self._async_handle_event)

    @callback
    def _async_handle_event(self, *args, **kwargs) -> None:
        """Handle the event fired by the functional channel."""
        raised_channel_event = self._get_channel_event_from_args(*args)

        if not self._should_raise(raised_channel_event):
            return

        event_types = self.entity_description.event_types
        if TYPE_CHECKING:
            assert event_types is not None

        self._trigger_event(event_type=event_types[0])
        self.async_write_ha_state()

    def _should_raise(self, event_type: str) -> bool:
        """Check if the event should be raised."""
        if self.entity_description.channel_event_types is None:
            return False
        return event_type in self.entity_description.channel_event_types

    def _get_channel_event_from_args(self, *args) -> str:
        """Get the channel event."""
        if isinstance(args[0], ChannelEvent):
            return args[0].channelEventType

        return ""
