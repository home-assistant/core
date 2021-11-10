"""Number entities for musiccast."""

from aiomusiccast.capabilities import NumberSetter

from homeassistant.components.number import NumberEntity
from homeassistant.components.yamaha_musiccast import (
    DOMAIN,
    MusicCastCapabilityEntity,
    MusicCastDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MusicCast sensor based on a config entry."""
    coordinator: MusicCastDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    number_entities = []

    for capability in coordinator.data.capabilities:
        if isinstance(capability, NumberSetter):
            number_entities.append(NumberCapability(coordinator, capability))

    for zone, data in coordinator.data.zones.items():
        for capability in data.capabilities:
            if isinstance(capability, NumberSetter):
                number_entities.append(NumberCapability(coordinator, capability, zone))

    async_add_entities(number_entities)


class NumberCapability(MusicCastCapabilityEntity, NumberEntity):
    """Representation of a MusicCast Alarm entity."""

    def __init__(
        self,
        coordinator: MusicCastDataUpdateCoordinator,
        capability: NumberSetter,
        zone_id: str = None,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, capability, zone_id)
        self._attr_min_value = capability.min_value
        self._attr_max_value = capability.max_value
        self._attr_step = capability.step

    @property
    def value(self):
        """Return the current."""
        return self.capability.current

    async def async_set_value(self, value: float):
        """Set a new value."""
        await self.capability.set(value)
