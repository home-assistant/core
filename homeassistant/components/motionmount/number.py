"""Support for MotionMount numeric control."""
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MotionMountEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Vogel's MotionMount from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            MotionMountExtension(coordinator, entry.entry_id),
            MotionMountTurn(coordinator, entry.entry_id),
        ]
    )


class MotionMountExtension(MotionMountEntity, NumberEntity):
    """The target extension position of a MotionMount."""

    _attr_name = "Extension"
    _attr_native_max_value = 100
    _attr_native_min_value = 0
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, unique_id):
        """Initialize Extension number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{unique_id}-extension"

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = self.coordinator.data["extension"]
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set the new value for extension."""
        await self.coordinator.mm.set_extension(value)


class MotionMountTurn(MotionMountEntity, NumberEntity):
    """The target turn position of a MotionMount."""

    _attr_name = "Turn"
    _attr_native_max_value = 100
    _attr_native_min_value = -100
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, unique_id):
        """Initialize Turn number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{unique_id}-turn"

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = self.coordinator.data["turn"]
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set the new value for turn."""
        await self.coordinator.mm.set_turn(value)
