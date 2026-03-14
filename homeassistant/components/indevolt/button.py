"""Button platform for Indevolt integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IndevoltConfigEntry
from .coordinator import IndevoltCoordinator
from .entity import IndevoltEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IndevoltButtonEntityDescription(ButtonEntityDescription):
    """Custom entity description class for Indevolt button entities."""

    generation: list[int] = field(default_factory=lambda: [1, 2])


BUTTONS: Final = (
    IndevoltButtonEntityDescription(
        key="stop",
        translation_key="stop",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndevoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button platform for Indevolt."""
    coordinator = entry.runtime_data
    device_gen = coordinator.generation

    # Button initialization
    async_add_entities(
        IndevoltButtonEntity(coordinator=coordinator, description=description)
        for description in BUTTONS
        if device_gen in description.generation
    )


class IndevoltButtonEntity(IndevoltEntity, ButtonEntity):
    """Represents a button entity for Indevolt devices."""

    entity_description: IndevoltButtonEntityDescription

    def __init__(
        self,
        coordinator: IndevoltCoordinator,
        description: IndevoltButtonEntityDescription,
    ) -> None:
        """Initialize the Indevolt button entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{self.serial_number}_{description.key}"

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.async_execute_realtime_action([0, 0, 0])
