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
from homeassistant.helpers.typing import UndefinedType

from .entity import HomematicipGenericEntity
from .hap import HomematicIPConfigEntry, HomematicipHAP


@dataclass(frozen=True, kw_only=True)
class HmipEventEntityDescription(EventEntityDescription):
    """Description of a HomematicIP Cloud event."""

    channel_event_types: list[str] | None = None
    channel_selector_fn: Callable[[FunctionalChannel], bool] | None = None
    event_type_map: dict[str, str] | None = None
    is_multi_channel: bool = False


EVENT_DESCRIPTIONS: tuple[HmipEventEntityDescription, ...] = (
    HmipEventEntityDescription(
        key="doorbell",
        translation_key="doorbell",
        device_class=EventDeviceClass.DOORBELL,
        event_types=["ring"],
        channel_event_types=["DOOR_BELL_SENSOR_EVENT"],
        event_type_map={"DOOR_BELL_SENSOR_EVENT": "ring"},
        channel_selector_fn=lambda channel: channel.channelRole == "DOOR_BELL_INPUT",
    ),
    HmipEventEntityDescription(
        key="button",
        translation_key="button",
        device_class=EventDeviceClass.BUTTON,
        event_types=["short_press", "long_press_start", "long_press_stop"],
        channel_event_types=[
            "KEY_PRESS_SHORT",
            "KEY_PRESS_LONG_START",
            "KEY_PRESS_LONG_STOP",
        ],
        event_type_map={
            "KEY_PRESS_SHORT": "short_press",
            "KEY_PRESS_LONG_START": "long_press_start",
            "KEY_PRESS_LONG_STOP": "long_press_stop",
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
        if description.channel_selector_fn and description.channel_selector_fn(channel)
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
            post=None if description.is_multi_channel else description.key,
            channel=channel.index,
            channel_real_index=channel.index if description.is_multi_channel else None,
            is_multi_channel=description.is_multi_channel,
            feature_id=description.key,
        )
        self.entity_description = description
        # Multi-channel events (e.g. WRC keypad buttons) are new entities
        # with no migration concerns, so opt them into has_entity_name and
        # let HA resolve the localized name via translation_key+placeholder.
        # The legacy single-channel path (doorbell) keeps the integration's
        # composed name property until the integration-wide has_entity_name
        # migration lands.
        if description.is_multi_channel:
            self._attr_has_entity_name = True
            self._attr_translation_placeholders = {"channel": str(channel.index)}

    @property
    def name(self) -> str | UndefinedType | None:
        """Return the entity name.

        For multi-channel events, bypass HmIP's legacy name composition
        and use HA's standard resolution (``translation_key`` +
        ``translation_placeholders``). For single-channel events
        (doorbell), keep the base class's composed name.
        """
        if self.entity_description.is_multi_channel:
            platform_translations = (
                self.platform_data.platform_translations if self.platform_data else {}
            )
            return self._name_internal(self._device_class_name, platform_translations)
        return super().name

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        channel = self.get_channel_or_raise()
        channel.add_on_channel_event_handler(self._async_handle_event)

    @callback
    def _async_handle_event(self, *args, **kwargs) -> None:
        """Handle the event fired by the functional channel."""
        raised_channel_event = self._get_channel_event_from_args(*args)
        event_type_map = self.entity_description.event_type_map
        if event_type_map is None:
            return
        public_event = event_type_map.get(raised_channel_event)
        if public_event is None:
            return
        self._trigger_event(event_type=public_event)
        self.async_write_ha_state()

    def _get_channel_event_from_args(self, *args) -> str:
        """Get the channel event."""
        if isinstance(args[0], ChannelEvent):
            return args[0].channelEventType

        return ""
