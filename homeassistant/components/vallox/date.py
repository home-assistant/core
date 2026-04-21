"""Support for Vallox date platform."""

from __future__ import annotations

from datetime import date

from homeassistant.components.date import DateEntity
from homeassistant.const import CONF_NAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ValloxConfigEntry, ValloxDataUpdateCoordinator
from .entity import ValloxEntity


class ValloxFilterChangeDateEntity(ValloxEntity, DateEntity):
    """Representation of a Vallox filter change date entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "filter_change_date"

    def __init__(
        self,
        name: str,
        coordinator: ValloxDataUpdateCoordinator,
    ) -> None:
        """Initialize the Vallox date."""
        super().__init__(name, coordinator)

        self._attr_unique_id = f"{self._device_uuid}-filter_change_date"

    @property
    def native_value(self) -> date | None:
        """Return the latest value."""

        return self.coordinator.data.filter_change_date

    async def async_set_value(self, value: date) -> None:
        """Change the date."""

        await self.coordinator.client.set_filter_change_date(value)
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ValloxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vallox filter change date entity."""
    coordinator = entry.runtime_data

    async_add_entities(
        [ValloxFilterChangeDateEntity(entry.data[CONF_NAME], coordinator)]
    )
