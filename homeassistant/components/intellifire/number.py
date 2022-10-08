"""Flame height number sensors."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import IntellifireDataUpdateCoordinator
from .entity import IntellifireEntity


@dataclass
class IntellifireFlameControlEntity(IntellifireEntity, NumberEntity):
    """Flame height control entity."""

    _attr_native_max_value: float = 5
    _attr_native_min_value: float = 1
    _attr_native_step: float = 1
    _attr_mode: NumberMode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: IntellifireDataUpdateCoordinator,
        description: NumberEntityDescription,
    ) -> None:
        """Initilaize Flame height Sensor."""
        super().__init__(coordinator, description)

    @property
    def native_value(self) -> float | None:
        """Return the current Flame Height segment number value."""
        value = self.coordinator.read_api.data.flameheight + 1
        LOGGER.debug("%s Value: %s", self._attr_name, value)
        return value

    async def async_set_native_value(self, value: float) -> None:
        """Slider change."""
        value_to_send: int = int(value) - 1
        LOGGER.debug(
            "%s set flame height to %d with raw value %s",
            self._attr_name,
            value,
            value_to_send,
        )
        await self.coordinator.control_api.set_flame_height(height=value_to_send)
        await self.async_update_ha_state(force_refresh=True)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fans."""
    coordinator: IntellifireDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    description = NumberEntityDescription(
        key="flame_control",
        name="Flame control",
        icon="mdi:arrow-expand-vertical",
    )
    entity = IntellifireFlameControlEntity(
        coordinator=coordinator, description=description
    )

    async_add_entities([entity])
