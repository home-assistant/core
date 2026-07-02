"""Select platform for Besen BS20."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from besen_bs20.models import BesenBS20Data

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BesenBS20ConfigEntry
from .const import LANGUAGES, TEMPERATURE_UNITS
from .coordinator import BesenBS20Coordinator
from .entity import BesenBS20Entity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BesenSelectEntityDescription(SelectEntityDescription):
    """Besen select description."""

    value_fn: Callable[[BesenBS20Data], str | None]
    set_fn: Callable[[BesenBS20Coordinator, str], Awaitable[None]]


SELECTS: tuple[BesenSelectEntityDescription, ...] = (
    BesenSelectEntityDescription(
        key="language",
        name="Language",
        value_fn=lambda data: data.config.language,
        set_fn=lambda coordinator, value: coordinator.async_set_language(value),
        options=list(LANGUAGES),
        entity_category=EntityCategory.CONFIG,
    ),
    BesenSelectEntityDescription(
        key="temperature_unit",
        name="Temperature Unit",
        value_fn=lambda data: data.config.temperature_unit,
        set_fn=lambda coordinator, value: coordinator.async_set_temperature_unit(value),
        options=list(TEMPERATURE_UNITS),
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BesenBS20ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Besen BS20 selects."""

    async_add_entities(
        [
            BesenBS20Select(entry.runtime_data.coordinator, description)
            for description in SELECTS
        ]
    )


class BesenBS20Select(BesenBS20Entity, SelectEntity):
    """Besen BS20 select."""

    entity_description: BesenSelectEntityDescription

    def __init__(
        self,
        coordinator: BesenBS20Coordinator,
        description: BesenSelectEntityDescription,
    ) -> None:
        """Initialize the select."""

        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_options = list(description.options or [])

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected option."""

        data = self.coordinator.data or self.coordinator.client.state
        return self.entity_description.value_fn(data)

    @override
    async def async_select_option(self, option: str) -> None:
        """Select an option."""

        await self.entity_description.set_fn(self.coordinator, option)
