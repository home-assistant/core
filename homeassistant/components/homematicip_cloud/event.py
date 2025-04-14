"""Support for HomematicIP Cloud events."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homematicip.device import Device

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import HomematicipGenericEntity
from .hap import HomematicipHAP


@dataclass(frozen=True, kw_only=True)
class HmipEventEntityDescription(EventEntityDescription):
    """Description of a HomematicIP Cloud event."""


EVENT_DESCRIPTIONS = {
    "doorbell": HmipEventEntityDescription(
        key="doorbell",
        translation_key="doorbell",
        device_class=EventDeviceClass.DOORBELL,
        event_types=["ring"],
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP cover from a config entry."""
    hap = hass.data[DOMAIN][config_entry.unique_id]

    async_add_entities(
        HomematicipDoorBellEvent(
            hap,
            device,
            channel.index,
            EVENT_DESCRIPTIONS["doorbell"],
        )
        for device in hap.home.devices
        for channel in device.functionalChannels
        if channel.channelRole == "DOOR_BELL_INPUT"
    )


class HomematicipDoorBellEvent(HomematicipGenericEntity, EventEntity):
    """Event class for HomematicIP doorbell events."""

    _attr_device_class = EventDeviceClass.DOORBELL

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
        event_types = self.entity_description.event_types
        if TYPE_CHECKING:
            assert event_types is not None

        self._trigger_event(event_type=event_types[0])
        self.async_write_ha_state()
