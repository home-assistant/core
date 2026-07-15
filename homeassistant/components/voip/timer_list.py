"""Timer list for VoIP devices."""

from functools import partial

from homeassistant.components.timer_list import (
    InMemoryTimerListEntity,
    TimerListEntity,
    TimerListEvent,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VoipConfigEntry
from .assist_satellite import VoipAssistSatellite
from .const import DOMAIN
from .devices import VoIPDevice

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VoipConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a timer list for each VoIP device."""
    domain_data = config_entry.runtime_data.domain_data

    @callback
    def async_add_device(device: VoIPDevice) -> None:
        """Add a timer list for a newly created device."""
        async_add_entities([_make_entity(config_entry, device)])

    domain_data.devices.async_add_new_device_listener(async_add_device)

    async_add_entities(
        [_make_entity(config_entry, device) for device in domain_data.devices]
    )


def _make_entity(config_entry: VoipConfigEntry, device: VoIPDevice) -> TimerListEntity:
    """Create a timer list entity for a device and forward its events."""
    entity = InMemoryTimerListEntity(
        name="Timers",
        unique_id=f"{device.voip_id}-timer_list",
        device_info=DeviceInfo(identifiers={(DOMAIN, device.voip_id)}),
    )
    # Forward timer events to the satellite so it can announce them. The
    # satellite is only present during an active call, so look it up when an
    # event fires rather than binding to a specific instance here.
    config_entry.async_on_unload(
        entity.async_subscribe_updates(partial(_async_forward_timer_event, device))
    )
    return entity


@callback
def _async_forward_timer_event(device: VoIPDevice, event: TimerListEvent) -> None:
    """Forward a timer event to the device's satellite, if one is connected."""
    if isinstance(device.protocol, VoipAssistSatellite):
        device.protocol.async_handle_timer_event(event)
