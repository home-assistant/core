"""Support for MotionMount numeric control."""
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MotionMountCoordinator
from .entity import MotionMountEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Vogel's MotionMount from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    unique_id = format_mac(coordinator.mm.mac.hex())

    async_add_entities(
        [
            MotionMountExtension(coordinator, unique_id),
            MotionMountTurn(coordinator, unique_id),
        ]
    )


class MotionMountExtension(MotionMountEntity, NumberEntity):
    """The target extension position of a MotionMount."""

    _attr_native_max_value = 100
    _attr_native_min_value = 0
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "motionmount_extension"

    def __init__(self, coordinator: MotionMountCoordinator, unique_id: str) -> None:
        """Initialize Extension number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{unique_id}-extension"

    @property
    def native_value(self) -> float:
        """Get native value."""
        return float(self.coordinator.data["extension"])

    async def async_set_native_value(self, value: float) -> None:
        """Set the new value for extension."""
        await self.coordinator.mm.set_extension(int(value))


class MotionMountTurn(MotionMountEntity, NumberEntity):
    """The target turn position of a MotionMount."""

    _attr_native_max_value = 100
    _attr_native_min_value = -100
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "motionmount_turn"

    def __init__(self, coordinator: MotionMountCoordinator, unique_id: str) -> None:
        """Initialize Turn number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{unique_id}-turn"

    @property
    def native_value(self) -> float:
        """Get native value."""
        return float(self.coordinator.data["turn"]) * -1

    async def async_set_native_value(self, value: float) -> None:
        """Set the new value for turn."""
        await self.coordinator.mm.set_turn(int(value * -1))
