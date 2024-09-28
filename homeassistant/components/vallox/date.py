"""Support for Vallox date platform."""

from __future__ import annotations

from datetime import date

from vallox_websocket_api import Vallox

from homeassistant.components.date import DateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ValloxDataUpdateCoordinator
from .entity import ValloxEntity


class ValloxFilterChangeDateEntity(ValloxEntity, DateEntity):
    """Representation of a Vallox filter change date entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "filter_change_date"

    def __init__(
        self,
        name: str,
        coordinator: ValloxDataUpdateCoordinator,
        client: Vallox,
    ) -> None:
        """Initialize the Vallox date."""
        super().__init__(name, coordinator)

        self._attr_unique_id = f"{self._device_uuid}-filter_change_date"
        self._client = client

    @property
    def native_value(self) -> date | None:
        """Return the latest value."""

        return self.coordinator.data.filter_change_date

    async def async_set_value(self, value: date) -> None:
        """Change the date."""

        await self._client.set_filter_change_date(value)
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vallox filter change date entity."""

    data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            ValloxFilterChangeDateEntity(
                data["name"], data["coordinator"], data["client"]
            )
        ]
    )
