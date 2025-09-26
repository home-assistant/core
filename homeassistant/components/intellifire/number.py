"""Flame height number sensors."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .coordinator import IntellifireConfigEntry, IntellifireDataUpdateCoordinator
from .entity import IntellifireEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntellifireConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the fans."""
    coordinator = entry.runtime_data

    description = NumberEntityDescription(
        key="flame_control",
        translation_key="flame_control",
    )

    async_add_entities(
        [
            IntellifireFlameControlEntity(
                coordinator=coordinator, description=description
            )
        ]
    )


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
        """Initialize Flame height Sensor."""
        super().__init__(coordinator, description)

    @property
    def native_value(self) -> float | None:
        """Return the current Flame Height segment number value."""
        # UI uses 1-5 for flame height, backing lib uses 0-4
        return self.coordinator.read_api.data.flameheight + 1

    async def async_set_native_value(self, value: float) -> None:
        """Slider change."""
        value_to_send: int = int(value) - 1
        LOGGER.debug(
            "%s set flame height to %d with raw value %s",
            self.name,
            value,
            value_to_send,
        )
        await self.coordinator.control_api.set_flame_height(height=value_to_send)
        await self.coordinator.async_refresh()
