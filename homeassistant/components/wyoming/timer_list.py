"""Timer list for Wyoming satellites."""

from functools import partial

from homeassistant.components.timer_list import InMemoryTimerListEntity, TimerListEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .models import DomainDataItem, WyomingConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WyomingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the timer list for a Wyoming satellite device."""
    item = entry.runtime_data
    device = item.device
    assert device is not None

    entity = InMemoryTimerListEntity(
        name="Timers",
        unique_id=f"{device.satellite_id}-timer_list",
        device_info=DeviceInfo(
            identifiers={(DOMAIN, device.satellite_id)},
            entry_type=DeviceEntryType.SERVICE,
        ),
    )
    async_add_entities([entity])

    # Forward timer events to the satellite so it can play sounds. The satellite
    # is connection-scoped, so look it up when an event fires rather than
    # binding to a specific instance here.
    entry.async_on_unload(
        entity.async_subscribe_updates(partial(_async_forward_timer_event, item))
    )


@callback
def _async_forward_timer_event(item: DomainDataItem, event: TimerListEvent) -> None:
    """Forward a timer event to the satellite, if one is connected."""
    if (satellite := item.satellite) is not None:
        satellite.handle_timer_event(event)
