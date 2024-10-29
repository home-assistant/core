"""Support for MotionMount numeric control."""

import socket

import motionmount

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MotionMountEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Vogel's MotionMount from a config entry."""
    mm: motionmount.MotionMount = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        (
            MotionMountExtension(mm, entry),
            MotionMountTurn(mm, entry),
        )
    )


class MotionMountExtension(MotionMountEntity, NumberEntity):
    """The target extension position of a MotionMount."""

    _attr_native_max_value = 100
    _attr_native_min_value = 0
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "motionmount_extension"

    def __init__(self, mm: motionmount.MotionMount, config_entry: ConfigEntry) -> None:
        """Initialize Extension number."""
        super().__init__(mm, config_entry)
        self._attr_unique_id = f"{self._base_unique_id}-extension"

    @property
    def native_value(self) -> float:
        """Get native value."""
        return float(self.mm.extension or 0)

    async def async_set_native_value(self, value: float) -> None:
        """Set the new value for extension."""
        try:
            await self.mm.set_extension(int(value))
        except (TimeoutError, socket.gaierror) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_communication",
            ) from ex


class MotionMountTurn(MotionMountEntity, NumberEntity):
    """The target turn position of a MotionMount."""

    _attr_native_max_value = 100
    _attr_native_min_value = -100
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "motionmount_turn"

    def __init__(self, mm: motionmount.MotionMount, config_entry: ConfigEntry) -> None:
        """Initialize Turn number."""
        super().__init__(mm, config_entry)
        self._attr_unique_id = f"{self._base_unique_id}-turn"

    @property
    def native_value(self) -> float:
        """Get native value."""
        return float(self.mm.turn or 0) * -1

    async def async_set_native_value(self, value: float) -> None:
        """Set the new value for turn."""
        try:
            await self.mm.set_turn(int(value * -1))
        except (TimeoutError, socket.gaierror) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_communication",
            ) from ex
