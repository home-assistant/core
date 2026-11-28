"""Timer list for Wyoming satellites."""

from typing import override

from homeassistant.components.timer_list import InMemoryTimerListEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .devices import SatelliteDevice
from .entity import WyomingSatelliteEntity
from .models import WyomingConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WyomingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the timer list of a Wyoming satellite."""
    device = config_entry.runtime_data.device
    assert device is not None

    async_add_entities([WyomingTimerList(device)])


class WyomingTimerList(WyomingSatelliteEntity, InMemoryTimerListEntity):
    """Timers of a Wyoming satellite."""

    entity_description = EntityDescription(key="timers", translation_key="timers")

    def __init__(self, device: SatelliteDevice) -> None:
        """Initialize the timer list."""
        WyomingSatelliteEntity.__init__(self, device)
        InMemoryTimerListEntity.__init__(self)

    @override
    async def async_added_to_hass(self) -> None:
        """Forward timer events to the satellite."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.async_subscribe_updates(self._device.handle_timer_event)
        )
