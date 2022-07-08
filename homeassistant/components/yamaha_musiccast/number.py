"""Number entities for musiccast."""

from aiomusiccast.capabilities import NumberSetter

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, MusicCastCapabilityEntity, MusicCastDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MusicCast number entities based on a config entry."""
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
    """Representation of a MusicCast Number entity."""

    capability: NumberSetter

    def __init__(
        self,
        coordinator: MusicCastDataUpdateCoordinator,
        capability: NumberSetter,
        zone_id: str = None,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, capability, zone_id)
        self._attr_native_min_value = capability.value_range.minimum
        self._attr_native_max_value = capability.value_range.maximum
        self._attr_native_step = capability.value_range.step

    @property
    def native_value(self):
        """Return the current value."""
        return self.capability.current

    async def async_set_native_value(self, value: float):
        """Set a new value."""
        await self.capability.set(value)
