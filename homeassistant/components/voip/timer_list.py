"""VoIP timer list entities."""

from typing import override

from homeassistant.components.timer_list import (
    InMemoryTimerListEntity,
    TimerListEvent,
    TimerListEventType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VoipConfigEntry
from .assist_satellite import VoipAssistSatellite
from .devices import VoIPDevice
from .entity import VoIPEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VoipConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up VoIP timer list entities."""
    domain_data = config_entry.runtime_data.domain_data

    @callback
    def async_add_device(device: VoIPDevice) -> None:
        """Add device."""
        async_add_entities([VoIPTimerList(device)])

    domain_data.devices.async_add_new_device_listener(async_add_device)

    async_add_entities([VoIPTimerList(device) for device in domain_data.devices])


class VoIPTimerList(VoIPEntity, InMemoryTimerListEntity):
    """Timer list holding the voice timers of a VoIP device."""

    entity_description = EntityDescription(key="timers", translation_key="timers")

    def __init__(self, voip_device: VoIPDevice) -> None:
        """Initialize the timer list."""
        VoIPEntity.__init__(self, voip_device)
        InMemoryTimerListEntity.__init__(self)

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to timer completion events."""
        await super().async_added_to_hass()
        self.async_on_remove(self.async_subscribe_updates(self._async_forward_event))

    @callback
    def _async_forward_event(self, event: TimerListEvent) -> None:
        """Announce finished timers on the satellite, if there is one."""
        if event.event_type != TimerListEventType.FINISHED:
            return
        if isinstance(satellite := self.voip_device.protocol, VoipAssistSatellite):
            satellite.async_announce_timer(event.item)
